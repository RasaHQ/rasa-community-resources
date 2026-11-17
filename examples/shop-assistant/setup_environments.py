"""Create absent locked environments; check and reuse existing owned ones."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def ensure(project, owner, runner=subprocess.run):
    project = Path(project).absolute()
    env = project / '.venv'
    if not env.exists():
        runner([sys.executable, '../../scripts/workspace.py', 'start', str(project), '--owner', owner], check=True)
        return 'created'
    try:
        if env.is_symlink() or not (env / 'bin/python').is_file():
            raise ValueError('environment path')
        record = json.loads((env / '.rasa-workspace.json').read_text())
        inputs = {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
                  for name in ('pyproject.toml', 'uv.lock')}
        if record['owner'] != owner or record['project'] != str(project) or record['inputs'] != inputs:
            raise ValueError('ownership or lock mismatch')
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError(f'Cannot reuse {project.name}/.venv: its ownership or lock inputs differ. Preserve this environment and use a fresh README-button Codespace; setup will not replace it.') from None
    print(f'Reusing {project.name}/.venv: owner and lock inputs match.')
    return 'reused'


def main():
    try:
        for path, owner in [('.', 'shop-native'), ('server', 'shop-server'), ('consent', 'shop-consent')]:
            ensure(path, owner)
    except (ValueError, subprocess.CalledProcessError) as error:
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        else:
            print('Locked environment installation failed. Check the setup output above; no existing environment was replaced.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
