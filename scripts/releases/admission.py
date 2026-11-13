"""Cheap catalog release decision before wheel downloads or licensed work."""
import json
import os
from pathlib import Path
import subprocess
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from index import candidates, get_json

INDEX = 'https://pypi.org/pypi/rasa-pro/json'
HOLD = Path('RASA_RELEASE_HOLD.json')


def held(version, hold):
    """The hold that keeps this version from being proposed, or None."""
    if not hold:
        return None
    if not hold.get('reason') or not hold.get('held'):
        raise ValueError('A release hold needs both held and reason')
    return hold if SpecifierSet(hold['held'], prereleases=True).contains(version) else None


def decide(current, data, open_prs=(), owner=None, hold=None):
    versions = candidates(data)
    if not versions:
        raise ValueError('No usable Rasa release found')
    latest = str(Version(versions[-1]))
    if Version(latest) < Version(current):
        raise ValueError('Index would downgrade the catalog; investigation required')
    if Version(latest) == Version(current):
        return {'status': 'unchanged', 'version': latest}
    reason = held(latest, hold)
    if reason:
        return {'status': 'held', 'version': latest, 'held': reason['held'], 'reason': reason['reason']}
    branch = 'automation/rasa-' + latest
    for pr in open_prs:
        if (pr['headRefName'] == branch and pr['baseRefName'] == 'main'
                and pr['headRepositoryOwner']['login'].lower() == owner.lower()):
            return {'status': 'open-candidate', 'version': latest, 'pr': pr['url']}
    return {'status': 'candidate', 'version': latest}


def check():
    data = get_json(INDEX)
    current = Path('RASA_PRO_VERSION').read_text().strip()
    hold = json.loads(HOLD.read_text()) if HOLD.exists() else None
    # An adopted or held version needs no GitHub request either.
    result = decide(current, data, hold=hold)
    if result['status'] != 'candidate':
        return result
    repo = os.environ.get('GITHUB_REPOSITORY')
    if not repo or os.environ.get('GITHUB_ACTIONS') != 'true':
        return result
    branch = 'automation/rasa-' + result['version']
    prs = json.loads(subprocess.check_output(
        ['gh', 'pr', 'list', '--repo', repo, '--head', branch, '--base', 'main',
         '--state', 'open', '--json', 'url,headRefName,baseRefName,headRepositoryOwner'], text=True))
    return decide(current, data, prs, repo.split('/')[0], hold)
