"""Run trusted maintenance gates and retain a redacted, reproducible repair packet."""
from pathlib import Path
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone

DEFAULT_OUTPUT = Path('/tmp/rasa-release-maintenance')


def redact(text, env=None):
    env = os.environ if env is None else env
    values = [v for k, v in env.items() if v and any(s in k.upper() for s in
              ('KEY', 'TOKEN', 'LICENSE', 'SECRET', 'PASSWORD', 'AUTHORIZATION'))]
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, '[REDACTED]')
    return re.sub(r'(https?://)[^/\s:@]+:[^/\s@]+@', r'\1[REDACTED]@', text)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def execute(label, command, output, timeout=2400):
    started = datetime.now(timezone.utc).isoformat()
    path = output / (label + '.log')
    print(redact(f'Running {label}: {shlex.join(command)}'), flush=True)
    try:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        code, text = result.returncode, result.stdout
    except subprocess.TimeoutExpired as error:
        text = error.stdout or ''
        if isinstance(text, bytes):
            text = text.decode(errors='replace')
        code, text = 124, text + f'\nTimed out after {timeout} seconds.'
    except OSError as error:
        code, text = 127, str(error)
    text = redact(text)
    path.write_text(text)
    print(text[-12000:], flush=True)
    return {'step': label, 'command': command, 'exitCode': code,
            'startedAt': started, 'log': path.name}


def advice(step, text):
    if 'Companion catalog has not adopted' in text:
        return ('companion-update', 'Run the companion release workflow first. Inspect its repair packet or merge its tested candidate; then rerun the website workflow. Never point the site at an untested companion commit.')
    if any(s in text for s in ('RASA_LICENSE missing', 'OPENAI_API_KEY missing', 'Missing required credentials')):
        return ('credentials', 'Restore the named GitHub Actions repository secrets and rerun. Do not change content or mark licensed checks as skipped.')
    if any(s in text for s in ('lacks rasa.mantle', 'does not ship rasa.mantle')):
        return ('engine-migration', 'Inspect the new wheel and upstream Rasa release notes. Adapt the maintained projects and tutorials to the new API, then rerun licensed training, SDK contracts and article review. Do not silently select an older release.')
    if step == 'proposal':
        return ('github-publication', 'Inspect proposal.json and the PR. Resolve branch conflicts, token permissions or required GitHub checks/reviews. The tested PR remains available when merging is blocked. Do not bypass repository protections. Rerun maintenance to retest before retrying publication.')
    if step == 'discovery':
        return ('release-preparation', 'Inspect discovery.json, the PyPI wheel hash and the failed command. For network/index errors retry the workflow. For dependency resolution errors reproduce the migration in a separate worktree and resolve the affected project locks.')
    return ('compatibility', 'Reproduce the failed command below. Use the per-project logs and candidate.patch to locate the affected API, fixture or code fence. Fix runnable examples and the matching article together; preserve historical verification claims. Regenerate the compatibility receipt and run the complete gates. Substantive article changes require fresh audience assessments.')


def handoff(output, kind, job_status=None):
    output.mkdir(parents=True, exist_ok=True)
    state_path = output / 'run.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'steps': [], 'status': 'setup-failed'}
    if job_status in ('failure', 'cancelled') and state.get('status') == 'passed':
        state['status'] = job_status
    failures = [s for s in state['steps'] if s['exitCode']]
    failed = failures[-1] if failures else None
    text = (output / failed['log']).read_text() if failed else ''
    category, recommendation = advice(failed['step'] if failed else 'setup', text)
    repo = os.environ.get('GITHUB_REPOSITORY', 'local')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    state.update({'repository': repo, 'kind': kind,
                  'runUrl': f'https://github.com/{repo}/actions/runs/{run_id}' if run_id else None})
    for name in ('RASA_RELEASE.json', 'COMPATIBILITY.json'):
        if Path(name).exists():
            (output / name).write_text(redact(Path(name).read_text()))
    patch = subprocess.run(['git', 'diff', '--binary', 'HEAD'], capture_output=True, text=True)
    if patch.stdout or not (output / 'candidate.patch').exists():
        (output / 'candidate.patch').write_text(redact(patch.stdout))
    # Collect SDK/training diagnostics without credentials or bulky environments.
    for directory in ('/tmp/rasa-catalog-compatibility', '/tmp/rasa-compatibility-live'):
        source = Path(directory)
        if source.exists():
            for file in source.rglob('*'):
                if file.is_file() and not file.is_symlink() and file.suffix in ('.log', '.json', '.txt'):
                    target = output / source.name / file.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(redact(file.read_text(errors='replace')))
    state['category'] = category if state['status'] != 'passed' else 'passed'
    state['recommendation'] = recommendation if state['status'] != 'passed' else 'Routine maintenance passed. Netlify production deployment still requires the operator.'
    write_json(state_path, state)
    lines = ['# Rasa maintenance handoff', '', f"Status: **{state['status']}**", '',
             f"Repository: `{repo}`", f"Source commit: `{state.get('sourceCommit', 'setup did not complete')}`",
             f"Workflow: {state['runUrl'] or 'local run'}", '', state['recommendation'], '',
             '## Commands and outcomes', '', '| Step | Exit | Reproduce |', '| --- | ---: | --- |']
    for result in state['steps']:
        lines.append(f"| {result['step']} | {result['exitCode']} | `{shlex.join(result['command'])}` |")
    lines += ['', '## Resume in a Codex session', '',
              '1. Clone the repository and check out the source commit above in a clean worktree.',
              '2. Download this run’s `rasa-release-maintenance` artifact. Read `run.json`, `discovery.json` (when present), and the failed step log.',
              '3. Inspect `candidate.patch` before applying it. If `proposal.json` names a candidate commit, fetch that branch instead. Restore required credentials through the environment, never in source.',
              '4. Reproduce the failed command, fix the cause and rerun `uv run --with packaging==26.3 python scripts/releases/maintenance.py --kind ' + kind + (' --companion companion' if kind == 'site' else '') + '`.',
              '5. Keep all gates enabled. Article semantics need audience review; generated pins and rendered version tokens update programmatically. Netlify approval remains manual.', '']
    if kind == 'site':
        lines += ['The website requires a clean clone of `RasaHQ/rasa-community-resources` at `companion/`. Discovery selects its tested commit before website checks.', '']
    report = redact('\n'.join(lines))
    (output / 'HANDOFF.md').write_text(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write(report)
    return state


def run(kind, companion, output, merge=False):
    output.mkdir(parents=True, exist_ok=True)
    state = {'status': 'running', 'steps': [], 'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}
    def step(label, command, timeout=2400):
        result = execute(label, command, output, timeout)
        state['steps'].append(result)
        state['status'] = 'failed' if result['exitCode'] else 'running'
        write_json(output / 'run.json', state)
        if result['exitCode']:
            raise RuntimeError(label)
    try:
        step('release-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts/releases'])
        command = [sys.executable, 'scripts/releases/update.py', '--report', str(output / 'discovery.json')]
        if kind == 'site':
            command += ['--companion', companion]
        step('discovery', command)
        if not all(os.environ.get(key) for key in ('RASA_LICENSE', 'OPENAI_API_KEY')):
            step('credentials', [sys.executable, '-c', "import os,sys; missing=[k for k in ('RASA_LICENSE','OPENAI_API_KEY') if not os.environ.get(k)]; print('Missing required credentials: '+', '.join(missing)); sys.exit(bool(missing))"])
        if kind == 'site':
            revision = json.loads(Path('RASA_RELEASE.json').read_text())['companionRevision']
            if not re.fullmatch(r'[a-f0-9]{40}', revision):
                raise ValueError('Invalid companion commit')
            step('companion-fetch', ['git', '-C', companion, 'fetch', 'origin', revision])
            step('companion-checkout', ['git', '-C', companion, 'checkout', '--detach', revision])
            step('compatibility', ['node', 'scripts/compatibility/report.mjs', '--companion', companion, '--live'])
            step('social-images', ['make', 'og'])
            step('site-gates', ['make', 'verify'])
            step('download', [sys.executable, 'scripts/check-quickstart-project.py'])
            step('live-regressions', ['uv', 'run', '--project', 'examples/quickstart', 'python', '-m', 'unittest', 'discover', '-s', 'scripts/compatibility'])
        else:
            step('catalog-gates', ['make', 'ci', 'KEEP_GOING=1'])
            step('compatibility', [sys.executable, 'scripts/compatibility.py', '--train', '--logs', '/tmp/rasa-catalog-compatibility'])
        # Publication is explicit: local reproduction never pushes or merges.
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            command = [sys.executable, 'scripts/releases/propose.py', '--state', str(output / 'proposal.json')]
            if merge:
                command.append('--merge')
            candidate = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], text=True)
            (output / 'candidate.patch').write_text(redact(candidate))
            step('proposal', command)
        state['status'] = 'passed'
        write_json(output / 'run.json', state)
        return 0
    except Exception as error:
        state['status'] = 'failed'
        state['error'] = redact(str(error))
        write_json(output / 'run.json', state)
        print(f'Maintenance failed: {redact(str(error))}', file=sys.stderr)
        return 1
    finally:
        handoff(output, kind)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['site', 'catalog'], required=True)
    parser.add_argument('--companion', default='companion')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--merge', action='store_true')
    parser.add_argument('--report-only', action='store_true')
    parser.add_argument('--job-status')
    args = parser.parse_args()
    if args.report_only:
        handoff(args.output, args.kind, args.job_status)
        return 0
    return run(args.kind, args.companion, args.output, args.merge)


if __name__ == '__main__':
    raise SystemExit(main())
