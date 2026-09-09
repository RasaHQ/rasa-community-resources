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
from rasa_projects import REPO_ROOT, discover_projects, read_expected_version
from check_project import _load_dotenv


def fingerprint(root, prefix=''):
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root).decode().split('\0')
    files = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(names) if name and name.startswith(prefix) and (root/name).is_file() and name != 'COMPATIBILITY.json'}
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('COMPATIBILITY.json'))
    parser.add_argument('--logs', type=Path, default=Path('/tmp/rasa-catalog-compatibility'))
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    _load_dotenv(REPO_ROOT)
    os.environ['RASA_TELEMETRY_ENABLED'] = 'false'
    secrets = [v for k,v in os.environ.items() if any(s in k.upper() for s in ('KEY','TOKEN','LICENSE','SECRET','PASSWORD')) and len(v)>8]
    def run(label, command, cwd=REPO_ROOT):
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=360)
        output = result.stdout + result.stderr
        for secret in secrets: output = output.replace(secret, '[REDACTED]')
        (args.logs/(label.replace('/','-')+'.log')).write_text(output)
        if result.returncode: raise RuntimeError(f'{label} failed; see redacted log in {args.logs}')
        print(f'PASS {label}', flush=True)
    run('tooling', [sys.executable, 'scripts/test_tooling.py'])
    run('migration-regressions', [sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_release_migration.py'])
    projects=[]
    for project in discover_projects():
        rel=project.path.relative_to(REPO_ROOT).as_posix()
        command=[sys.executable,'scripts/check_project.py',rel]
        if args.train: command += ['--train','--require-license','--require-secrets']
        run(rel, command)
        checks=['locked-install','installed-version','mantle-import','project-validation']
        if args.train: checks.append('licensed-training')
        if (project.path/'tests').is_dir():
            run(rel+'-tests',['uv','run','--locked','python','-m','unittest','discover','-s','tests','-v'],project.path)
            checks.append('project-unittests')
        if rel=='tutorials/rasa-hubspot-crm-tutorial':
            run(rel+'-mcp',['uv','run','--locked','python','scripts/prove_mcp_swap.py'],project.path)
            checks.append('mock-mcp-transport-proof')
        if rel=='tutorials/rasa-ai-team-casebook':
            run(rel+'-sdk',['uv','run','--locked','python',str(REPO_ROOT/'scripts/check_casebook_sdk.py')],project.path)
            checks += ['62-scenario-oracles','186-mutations-killed','62-sdk-tool-dispatches']
        projects.append({'path':rel,'sourceHash':fingerprint(REPO_ROOT,rel+'/'),'checks':checks,'liveConversations':'not tested'})
    run('starter-pack',['uv','run','--project','tutorials/rasa-ai-team-casebook','python','scripts/check_starter_pack.py'])
    report={'schema':1,'testedAt':datetime.now(timezone.utc).isoformat(),'version':read_expected_version(),'sourceHash':fingerprint(REPO_ROOT),'projects':projects,'starterPack':['scaffold-sdk-validation','lint-negative-controls'],'liveConversations':'not tested; separate website quickstart live acceptance covers four synthetic text cases only'}
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(projects)} maintained projects passed; {args.out}')


if __name__=='__main__': main()
