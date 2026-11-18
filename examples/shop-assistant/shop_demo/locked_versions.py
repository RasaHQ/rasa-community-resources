"""Check installed packages against this example's exact resolved lock."""
from importlib.metadata import version
from pathlib import Path
import tomllib


def require_locked_version(project, distribution):
    try:
        packages = tomllib.loads((Path(project) / 'uv.lock').read_text())['package']
        expected = {package['version'] for package in packages if package['name'] == distribution}
        if len(expected) != 1 or version(distribution) != next(iter(expected)):
            raise ValueError('lock mismatch')
    except Exception:
        raise RuntimeError('Use the example locked environment: installed ' + distribution + ' must match uv.lock. Run make setup in a fresh Codespace; preserve existing environments and state.') from None
