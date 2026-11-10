"""Execute the maintained catalog and record precisely what was tested.

Never marks live voice/vendor conversations tested. Training is a separate,
required mode for trusted release automation; pull requests use offline mode.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from rasa_projects import REPO_ROOT, discover_projects, read_expected_version, read_training_secrets
from check_project import _load_dotenv


def fingerprint(root, prefix=''):
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root).decode().split('\0')
    files = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(names) if name and name.startswith(prefix) and (root/name).is_file() and name != 'COMPATIBILITY.json'}
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def test_workers(project, root=REPO_ROOT):
    """Resolve declared isolated workers without expanding the Rasa catalog."""
    metadata = tomllib.loads((project / 'pyproject.toml').read_text())
    declared = metadata.get('tool', {}).get('rasa-catalog', {}).get('test-workers', [])
    if not isinstance(declared, list) or any(not isinstance(p, str) or not p for p in declared):
        raise ValueError('test-workers must be a list of project-relative paths')
    workers = []
    for name in declared:
        worker = (project / name).resolve()
        if Path(name).is_absolute() or not worker.is_relative_to(root.resolve()) or worker == project.resolve():
            raise ValueError('test-workers must name separate projects inside this repository')
        if not all((worker / file).is_file() for file in ('pyproject.toml', 'uv.lock')):
            raise ValueError(f'Test worker lacks locked rebuild inputs: {name}')
        if worker not in workers:
            workers.append(worker)
    return workers


class CheckRunner:
    """Keep failure evidence while allowing independent catalog checks to finish."""
    def __init__(self, logs, secrets, keep_going=False):
        self.logs, self.secrets, self.keep_going = logs, secrets, keep_going
        self.failures = []
        self.logs.mkdir(parents=True, exist_ok=True)

    def run(self, label, command, cwd=REPO_ROOT):
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=360)
        output = result.stdout + result.stderr
        for secret in self.secrets:
            output = output.replace(secret, '[REDACTED]')
        (self.logs / (label.replace('/', '-') + '.log')).write_text(output)
        if result.returncode:
            self.failures.append(label)
            print(f'FAIL {label}\n{output[-12000:]}', flush=True)
            if not self.keep_going:
                raise RuntimeError(f'{label} failed; see redacted log in {self.logs}')
            return False
        print(f'PASS {label}', flush=True)
        return True

    def finish(self):
        if self.failures:
            raise RuntimeError('Catalog checks failed: ' + ', '.join(self.failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('COMPATIBILITY.json'))
    parser.add_argument('--logs', type=Path, default=Path('/tmp/rasa-catalog-compatibility'))
    parser.add_argument('--local-embeddings', metavar='PROVIDER/MODEL', help='Validate training with this local embedder for references indexes (see check_project.py)')
    parser.add_argument('--placeholder-secret', action='append', default=[], metavar='NAME', help='Set NAME to an obviously fake value when unset. For provider keys that training must see defined but never calls; recorded in the report')
    parser.add_argument('--keep-going', action='store_true', help='Run later independent checks after a failure; still fail and do not write a success report')
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    _load_dotenv(REPO_ROOT)
    placeholders = [n for n in args.placeholder_secret if not os.environ.get(n, '').strip()]
    for name in placeholders: os.environ[name] = 'placeholder-not-a-real-key'
    os.environ['RASA_TELEMETRY_ENABLED'] = 'false'
    secrets = [v for k,v in os.environ.items() if any(s in k.upper() for s in ('KEY','TOKEN','LICENSE','SECRET','PASSWORD','CREDENTIAL')) and len(v)>8]
    runner = CheckRunner(args.logs, secrets, args.keep_going)
    run = runner.run
    run('tooling', [sys.executable, 'scripts/test_tooling.py'])
    run('migration-regressions', [sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_release_migration.py'])
    projects=[]
    for project in discover_projects():
        rel=project.path.relative_to(REPO_ROOT).as_posix()
        command=[sys.executable,'scripts/check_project.py',rel]
        if args.train: command += ['--train','--require-license','--require-secrets']
        if args.train and args.local_embeddings: command += ['--local-embeddings', args.local_embeddings]
        if not run(rel, command):
            continue
        checks=['locked-install','installed-version','mantle-import','project-validation']
        if args.train: checks.append(f'licensed-training (references embedded with {args.local_embeddings})' if args.local_embeddings and (project.path/'agent.yml').is_file() and ((project.path/'references').is_dir() or 'references:' in (project.path/'agent.yml').read_text()) else 'licensed-training')
        workers=[]
        if (project.path/'tests').is_dir():
            worker_ready = True
            for worker in test_workers(project.path):
                worker_rel = worker.relative_to(REPO_ROOT).as_posix()
                # These runtimes deliberately stay out of the Mantle environment.
                # Always sync the lock before executing the dependent native tests.
                if not run(worker_rel+'-worker-install', ['uv','sync','--locked','--project',str(worker)]):
                    worker_ready = False
                    continue
                workers.append({'path':worker_rel,'sourceHash':fingerprint(REPO_ROOT,worker_rel+'/'),'checks':['locked-install']})
            if not worker_ready:
                continue
            run(rel+'-tests',['uv','run','--locked','python','-m','unittest','discover','-s','tests','-v'],project.path)
            checks.append('project-unittests')
        if rel=='tutorials/rasa-hubspot-crm-tutorial':
            run(rel+'-mcp',['uv','run','--locked','python','scripts/prove_mcp_swap.py'],project.path)
            checks.append('mock-mcp-transport-proof')
        if rel=='tutorials/rasa-ai-team-casebook':
            run(rel+'-sdk',['uv','run','--locked','python',str(REPO_ROOT/'scripts/check_casebook_sdk.py')],project.path)
            checks += ['62-scenario-oracles','186-mutations-killed','62-sdk-tool-dispatches']
        entry={'path':rel,'sourceHash':fingerprint(REPO_ROOT,rel+'/'),'checks':checks,'liveConversations':'not tested'}
        if workers: entry['nativeTestWorkers'] = workers
        used=[n for n in placeholders if n in read_training_secrets(project)]
        if args.train and used: entry['placeholderSecrets']=used
        projects.append(entry)
    run('starter-pack',['uv','run','--project','tutorials/rasa-ai-team-casebook','python','scripts/check_starter_pack.py'])
    runner.finish()
    report={'schema':1,'testedAt':datetime.now(timezone.utc).isoformat(),'version':read_expected_version(),'sourceHash':fingerprint(REPO_ROOT),'projects':projects,'starterPack':['scaffold-sdk-validation','lint-negative-controls'],'liveConversations':'not tested; separate website quickstart live acceptance covers four synthetic text cases only'}
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(projects)} maintained projects passed; {args.out}')


if __name__=='__main__': main()
