"""Verified PyPI release discovery. No release-line fence or hand-written version sort."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
from datetime import datetime, timezone
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet

PACKAGE = 'rasa-pro'
REQUIRED_MODULE = 'rasa/mantle/'


def candidates(data):
    result = []
    for name, files in data['releases'].items():
        try:
            version = Version(name)
        except InvalidVersion:
            continue
        usable = [f for f in files if not f.get('yanked') and f['filename'].endswith('.whl') and (not f.get('requires_python') or Version('3.12') in SpecifierSet(f['requires_python']))]
        if usable:
            result.append((version, name))
    return [name for _, name in sorted(result)]


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def inspect_release(version, data=None, fetch=None):
    # Canonical PEP 440 spelling prevents path/query injection into the index URL.
    if str(Version(version)) != version:
        raise ValueError('A canonical PEP 440 version is required')
    data = data or get_json(f'https://pypi.org/pypi/{PACKAGE}/{version}/json')
    wheels = [f for f in data['urls'] if f['filename'].endswith('.whl') and not f.get('yanked') and (not f.get('requires_python') or Version('3.12') in SpecifierSet(f['requires_python']))]
    if not wheels:
        raise ValueError(f'{version}: no non-yanked wheel compatible with Python 3.12')
    wheel = min(wheels, key=lambda f: f['size'])
    if not wheel['url'].startswith('https://files.pythonhosted.org/'):
        raise ValueError('Unexpected wheel host')
    if fetch is None:
        def fetch(url):
            with urllib.request.urlopen(url, timeout=90) as response:
                return response.read()
    raw = fetch(wheel['url'])
    digest = hashlib.sha256(raw).hexdigest()
    if digest != wheel['digests']['sha256']:
        raise ValueError('Downloaded wheel does not match the PyPI SHA-256')
    names = zipfile.ZipFile(io.BytesIO(raw)).namelist()
    return {'version': version, 'wheel': wheel['filename'], 'wheelSha256': digest,
            'uploadedAt': wheel['upload_time_iso_8601'], 'requiresPython': wheel.get('requires_python'),
            'mantlePresent': any(name.startswith(REQUIRED_MODULE) for name in names)}


HOLD = Path(__file__).resolve().parents[2] / 'RASA_RELEASE_HOLD.json'


def load_hold(path=HOLD):
    return json.loads(path.read_text()) if path.exists() else None


def held(version, hold):
    """The hold that keeps this version from being adopted, or None."""
    if not hold:
        return None
    if not hold.get('reason') or not hold.get('held'):
        raise ValueError('A release hold needs both held and reason')
    return hold if SpecifierSet(hold['held'], prereleases=True).contains(version) else None


def unheld(versions, hold):
    return [v for v in versions if not held(v, hold)]


def discover(data=None, inspect=inspect_release, hold=None):
    data = data or get_json(f'https://pypi.org/pypi/{PACKAGE}/json')
    hold = load_hold() if hold is None else hold
    # A held release is never selected; the newest unheld release is.
    versions = unheld(candidates(data), hold)
    if not versions:
        raise ValueError('No usable Rasa release found')
    latest = versions[-1]
    stable = [v for v in versions if not Version(v).is_prerelease]
    selected = inspect(latest)
    latest_stable = inspect(stable[-1]) if stable and stable[-1] != latest else selected
    return {'schema': 1, 'checkedAt': datetime.now(timezone.utc).isoformat(),
            'index': 'https://pypi.org/pypi/rasa-pro/json',
            'policy': 'highest non-yanked PEP 440 wheel version for Python 3.12, including prereleases, outside RASA_RELEASE_HOLD.json; require rasa.mantle; never silently fall back',
            'selected': selected, 'latestStable': latest_stable}


if __name__ == '__main__':
    print(json.dumps(discover(), indent=2))
