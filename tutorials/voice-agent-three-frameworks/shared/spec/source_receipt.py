"""Source provenance for a run. Hash explicit source inputs; never read credentials."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

SOURCE_SUFFIXES = {'.py', '.yml', '.yaml', '.json', '.toml', '.lock', '.txt', '.md', '.diff'}
EXCLUDED = {'.venv', '__pycache__', 'results', 'raw', '.git', 'models', '.rasa', 'node_modules'}

def source_receipt(tutorial: Path, project: Path, framework: str) -> dict:
    files = {}
    for base in (project, tutorial / 'shared' / 'clinic', tutorial / 'shared' / 'speech', tutorial / 'shared' / 'spec'):
        for path in sorted(base.rglob('*')):
            if path.is_symlink() or not path.is_file() or any(p in EXCLUDED for p in path.relative_to(base).parts):
                continue
            if path.name.startswith('.env') or path.suffix not in SOURCE_SUFFIXES:
                continue
            relative = str(path.relative_to(tutorial)) if path.is_relative_to(tutorial) else str(path.relative_to(project))
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((tutorial / 'shared' / 'spec' / 'caller-audio').glob('*.wav')):
        if path.is_file() and not path.is_symlink():
            files[str(path.relative_to(tutorial))] = hashlib.sha256(path.read_bytes()).hexdigest()
    repository_files = {}
    router = tutorial.parents[1] / 'patterns/voice-vendor-router'
    # The external router package is part of the runtime, not a copied
    # framework implementation. Never traverse its environment or model data.
    selected = [router/'pyproject.toml', router/'uv.lock']
    selected += list((router/'voicerouter').rglob('*.py'))
    for path in sorted(selected):
        if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts:
            repository_files[str(path.relative_to(tutorial.parents[1]))] = hashlib.sha256(path.read_bytes()).hexdigest()
    expansion_path = tutorial / 'EXPANSION.json'
    if expansion_path.is_file():
        files['EXPANSION.json'] = hashlib.sha256(expansion_path.read_bytes()).hexdigest()
    def git(*args):
        result = subprocess.run(['git', '-C', str(tutorial), *args], capture_output=True, text=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    expansions = json.loads((tutorial / 'EXPANSION.json').read_text()) if (tutorial / 'EXPANSION.json').exists() else {}
    return {'git_head': git('rev-parse', 'HEAD'),
            'git_dirty': bool(git('status', '--porcelain', '--untracked-files=normal')),
            'framework': framework,
            'edition': 'Rasa Pro Mantle baseline' if framework == 'rasa' else 'community open-source SDK',
            'model': expansions.get('model'), 'reasoning_effort': expansions.get('reasoning_effort'),
            'transport_lane': 'common-browser-audio',
            'file_sha256': files,
            'repository_file_sha256': repository_files,
            'inputs_sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
