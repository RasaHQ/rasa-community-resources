"""Publish a tested, bounded candidate; normal GitHub rules still control merging."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def changed_identity(current, previous):
    return (current['selected']['version'], current.get('companionRevision')) != (previous['selected']['version'], previous.get('companionRevision'))


def allowed_path(path, site):
    if path in ('RASA_PRO_VERSION', 'RASA_RELEASE.json', 'COMPATIBILITY.json'):
        return True
    if site:
        return path in ('examples/quickstart/pyproject.toml', 'examples/quickstart/uv.lock', 'public/og.webp') or path.startswith('public/og/')
    if path in ('README.md', 'docs/MIGRATING.md', 'Makefile'):
        return True
    parts = Path(path).parts
    return (parts[0] in ('examples', 'tutorials', 'patterns', 'starter-pack', 'community') and
            (parts[-1] in ('pyproject.toml', 'uv.lock', 'Makefile') or path.endswith('.md')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=Path('/tmp/rasa-release-maintenance/proposal.json'))
    parser.add_argument('--merge', action='store_true')
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise SystemExit('Release publication runs only in trusted main-branch Actions.')
    current = json.loads(Path('RASA_RELEASE.json').read_text())
    previous = json.loads(git('show', 'HEAD:RASA_RELEASE.json'))
    state = {'status': 'unchanged', 'version': current['selected']['version']}
    args.state.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.state.write_text(json.dumps(state, indent=2) + '\n')
    save()
    if not changed_identity(current, previous):
        print('Adopted release passes; daily evidence is retained without a timestamp-only PR.')
        return
    base = git('rev-parse', 'HEAD')
    def require_tested_base():
        current_main = git('ls-remote', '--heads', 'origin', 'refs/heads/main').split()
        if not current_main or current_main[0] != base:
            raise SystemExit('Main changed during validation; rerun maintenance on its new head before publishing.')
    require_tested_base()
    version = state['version']
    if not re.fullmatch(r'[0-9][0-9a-z.]*', version):
        raise SystemExit('Invalid branch version')
    site = 'companionRevision' in current
    suffix = '-' + current['companionRevision'][:12] if site else ''
    branch = 'automation/rasa-' + version + suffix
    paths = subprocess.check_output(['git', 'diff', '--name-only', '-z', 'HEAD']).decode().strip('\0').split('\0')
    if not paths or any(not allowed_path(path, site) for path in paths):
        raise SystemExit('Unexpected candidate paths; leave source edits to a reviewed repair PR: ' + ', '.join(paths))
    # A digest binds the exact tested file contents, not a rebased or newly fetched tree.
    digest = hashlib.sha256(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'])).hexdigest()
    subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
    subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
    subprocess.run(['git', 'checkout', '-B', branch], check=True)
    subprocess.run(['git', 'add', '--', *paths], check=True)
    subprocess.run(['git', 'commit', '-m', f'Adopt tested Rasa Pro {version}'], check=True)
    head = git('rev-parse', 'HEAD')
    state.update({'branch': branch, 'head': head, 'testedDiffSha256': digest, 'status': 'committed'})
    save()
    remote = git('ls-remote', '--heads', 'origin', 'refs/heads/' + branch)
    old_head = remote.split()[0] if remote else ''
    subprocess.run(['git', 'push', f'--force-with-lease=refs/heads/{branch}:{old_head}', 'origin', f'HEAD:refs/heads/{branch}'], check=True)
    repo = os.environ['GITHUB_REPOSITORY']
    run_url = f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    body = f'''Update the maintained Rasa pin to {version} and its tested companion revision where applicable.

The PyPI wheel is SHA-256 verified. All required compatibility, training and content gates passed before publication. COMPATIBILITY.json records the scope; historical human verification claims are preserved.

Evidence and repair packet: {run_url} (artifact rasa-release-maintenance).
Tested commit: {head}. Candidate diff SHA-256: {digest}.

Routine updates may merge through the normal GitHub merge API after these gates; required reviews and branch protections still apply. Netlify deployment approval remains manual.
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md') as file:
        file.write(body)
        file.flush()
        prs = json.loads(subprocess.check_output(['gh', 'pr', 'list', '--repo', repo, '--head', branch, '--state', 'open', '--json', 'number'], text=True))
        if prs:
            number = str(prs[0]['number'])
            subprocess.run(['gh', 'pr', 'edit', number, '--repo', repo, '--title', f'Adopt tested Rasa Pro {version}', '--body-file', file.name], check=True)
        else:
            url = subprocess.check_output(['gh', 'pr', 'create', '--repo', repo, '--base', 'main', '--head', branch, '--title', f'Adopt tested Rasa Pro {version}', '--body-file', file.name], text=True).strip()
            number = url.rsplit('/', 1)[-1]
    state.update({'pr': f'https://github.com/{repo}/pull/{number}', 'status': 'proposed'})
    save()
    if args.merge:
        require_tested_base()
        # No --admin, direct trunk push, synthetic check or approval bypass.
        subprocess.run(['gh', 'pr', 'merge', number, '--repo', repo, '--merge', '--match-head-commit', head], check=True)
        merged = json.loads(subprocess.check_output(['gh', 'pr', 'view', number, '--repo', repo, '--json', 'state,mergeCommit'], text=True))
        if merged['state'] != 'MERGED':
            raise RuntimeError('Merge requires GitHub approval/checks; candidate retained for review.')
        state.update({'status': 'merged', 'mergeCommit': merged['mergeCommit']['oid']})
        save()
        # Token-originated pushes may not trigger CI. Explicit dispatch is supported.
        workflow = 'rasa-compatibility.yml' if site else 'validate.yml'
        subprocess.run(['gh', 'workflow', 'run', workflow, '--repo', repo, '--ref', 'main'], check=True)
        state['postMergeChecksDispatched'] = True
        save()


if __name__ == '__main__':
    main()
