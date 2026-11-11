"""Cheap catalog release decision before wheel downloads or licensed work."""
import json
import os
from pathlib import Path
import subprocess
from packaging.version import Version
from index import candidates, get_json

INDEX = 'https://pypi.org/pypi/rasa-pro/json'


def decide(current, data, open_prs=(), owner=None):
    versions = candidates(data)
    if not versions:
        raise ValueError('No usable Rasa release found')
    latest = str(Version(versions[-1]))
    if Version(latest) < Version(current):
        raise ValueError('Index would downgrade the catalog; investigation required')
    if Version(latest) == Version(current):
        return {'status': 'unchanged', 'version': latest}
    branch = 'automation/rasa-' + latest
    for pr in open_prs:
        if (pr['headRefName'] == branch and pr['baseRefName'] == 'main'
                and pr['headRepositoryOwner']['login'].lower() == owner.lower()):
            return {'status': 'open-candidate', 'version': latest, 'pr': pr['url']}
    return {'status': 'candidate', 'version': latest}


def check():
    data = get_json(INDEX)
    current = Path('RASA_PRO_VERSION').read_text().strip()
    # An adopted version needs no GitHub request either.
    result = decide(current, data)
    if result['status'] != 'candidate':
        return result
    repo = os.environ.get('GITHUB_REPOSITORY')
    if not repo or os.environ.get('GITHUB_ACTIONS') != 'true':
        return result
    branch = 'automation/rasa-' + result['version']
    prs = json.loads(subprocess.check_output(
        ['gh', 'pr', 'list', '--repo', repo, '--head', branch, '--base', 'main',
         '--state', 'open', '--json', 'url,headRefName,baseRefName,headRepositoryOwner'], text=True))
    return decide(current, data, prs, repo.split('/')[0])
