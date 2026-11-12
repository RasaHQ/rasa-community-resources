# SPDX-License-Identifier: MIT
"""One owned launcher for this example's mock, MCP host and native Inspector."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from urllib.parse import urlencode

from contract_inputs import ContractError,MissingContractInput,SymitarContract,load_inputs
from fixture_control import INSTANCE,current,reset
from journal import Journal
from local_transport import LocalTransport
from mock_server import FixtureState,SymitarMock,local_mock_server
from native_host import Gateway
from server import local_server
from vendor_client import SymitarClient

ROOT=Path(__file__).resolve().parent


def inspector_address(port):
    name=os.environ.get('CODESPACE_NAME')
    origin=(f"https://{name}-{port}.{os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev')}" if name else f'http://localhost:{port}')
    return origin,origin+'/webhooks/inspector/inspect.html?'+urlencode({'projectUrl':origin,'channel':'inspector'})


def stop_child(child):
    if child is None:return
    # The launcher starts this process group itself. A parent exit must not
    # leave its remaining children running with the private host capability.
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:
        child.wait();return
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        child.poll()
        try:os.killpg(child.pid,0)
        except ProcessLookupError:break
        time.sleep(.05)
    else:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    try:child.wait(timeout=3)
    except subprocess.TimeoutExpired:raise ValueError('owned_process_did_not_stop') from None



def cleanup(child,servers,threads,state,journal,previous):
    """Drain owned resources even if a second stop signal or child error arrives."""
    failed=[]
    def step(name,action):
        try:action()
        except (Exception,KeyboardInterrupt):failed.append(name)
    for sig in previous:
        step('signal',lambda sig=sig:signal.signal(sig,signal.SIG_IGN))
    try:
        step('child',lambda:stop_child(child))
        # shutdown waits for serve_forever; never call it on an unstarted server.
        for server,thread in reversed(list(zip(servers,threads))):
            if thread.is_alive():step('server',server.shutdown)
        for thread in threads:
            step('thread',lambda thread=thread:thread.join(timeout=10))
            if thread.is_alive():failed.append('thread')
        for server in servers:step('server_close',server.server_close)
        if state is not None:step('state',state.close)
        if journal is not None:step('journal',journal.close)
    finally:
        for sig,handler in previous.items():
            step('restore_signal',lambda sig=sig,handler=handler:signal.signal(sig,handler))
    return failed


def prepare_runtime(run,public_origin,*,text_api=False):
    """Keep the SDK's full Mantle layout when writing runtime-only settings."""
    from rasa.shared.utils.yaml import read_yaml_file,write_yaml
    integrations=read_yaml_file(ROOT/'integrations.yml',expand_env_vars=False)
    integrations['channels'].pop('rest',None)
    if text_api:integrations['channels']['rest']={'enabled':True}
    integrations['channels']['inspector']['server_url']=public_origin
    write_yaml(integrations,run/'integrations.yml')
    for relative in ('agent.yml','skills/banking/skill.md','skills/banking/tools.py'):
        target=run/relative;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/relative).read_bytes())


def child_environment():
    allowed={'PATH','HOME','TMPDIR','TMP','TEMP','LANG','LC_ALL','LC_CTYPE',
             'SSL_CERT_FILE','SSL_CERT_DIR','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE',
             'UV_CACHE_DIR','HF_HOME','HUGGINGFACE_HUB_CACHE','XDG_CACHE_HOME',
             'USER','LOGNAME','RASA_LICENSE','OPENAI_API_KEY','DEEPGRAM_API_KEY'}
    return {key:value for key,value in os.environ.items() if key in allowed}


def main():
    parser=argparse.ArgumentParser(description='Start this fictional Symitar voice example.')
    parser.add_argument('--port',type=int,default=5005)
    parser.add_argument('--text-api',action='store_true')
    parser.add_argument('--check-inputs',action='store_true')
    parser.add_argument('--reset-fixture',action='store_true')
    parser.add_argument('--ack-unknown',action='store_true')
    parser.add_argument('--reason',default='')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('choose an unprivileged port')
    if args.reset_fixture:
        try:reset(ROOT/'.runtime',acknowledge=args.ack_unknown,reason=args.reason)
        except Exception:
            print('Reset refused. Stop every copy first; preserve original state and supply acknowledgement plus a nonsecret reason.');return 2
        print('New fictional epoch created. Original state and audit are retained; no old transfer was resolved or retried.');return 0
    try:
        inputs=load_inputs();contract=SymitarContract(inputs)
    except MissingContractInput as error:
        print('Not ready. '+str(error));return 2
    except ContractError:
        print('Not ready. A vendor definition differs from its pinned bytes; preserve it and supply the exact official file.');return 2
    if args.check_inputs:
        print('All four manual vendor inputs match the pinned hashes and local references. No bank connection.');return 0
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env',override=False)
    missing=[key for key in ('RASA_LICENSE','OPENAI_API_KEY','DEEPGRAM_API_KEY') if not os.environ.get(key,'').strip()]
    if missing:
        print('Not ready. Add personal Codespaces secrets, allow repository access, then stop/reopen: '+', '.join(missing));return 2
    from importlib.metadata import version
    expected=next(dep.split('==')[1] for dep in tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['dependencies'] if dep.startswith('rasa-pro=='))
    if version('rasa-pro')!=expected:
        print('Not ready. Rebuild this folder with uv sync --locked; its SDK differs from the project pin.');return 2
    servers=[];threads=[];journal=state=child=None
    def interrupted(*_):raise KeyboardInterrupt()
    previous={sig:signal.signal(sig,interrupted) for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    try:
        record=current(ROOT/'.runtime',initialize=True);directory=ROOT/'.runtime'/record['directory']
        journal=Journal(directory/'journal',INSTANCE)
        if journal.epoch!=record['epoch']:raise ValueError('fixture_epoch_changed')
        state=FixtureState(directory/'mock.sqlite3',journal.epoch)
        fixture,_=state.snapshot();mock=SymitarMock(inputs,state)
        wire_key=secrets.token_urlsafe(32)
        wire=local_mock_server(mock,wire_key);servers.append(wire)
        transport=LocalTransport('http://127.0.0.1:'+str(wire.server_port),wire_key)
        gateway=Gateway(SymitarClient(transport,contract,fixture['institution']),journal,fixture)
        capability=secrets.token_urlsafe(32)
        host=local_server(None,capability,gateway=gateway);servers.append(host)
        for server in servers:
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.05});thread.start();threads.append(thread)
        environment=child_environment()
        environment.update(SYMITAR_HOST_URL='http://127.0.0.1:'+str(host.server_port),SYMITAR_HOST_CAPABILITY=capability)
        environment['PYTHONPATH']=str(ROOT)
        origin,url=inspector_address(args.port)
        with tempfile.TemporaryDirectory(prefix='symitar-run-') as temporary:
            run=Path(temporary).resolve();models=run/'models'
            # The normal native CLI path validates and packages this project.
            child=subprocess.Popen([sys.executable,'-m','rasa','train','--config',str(ROOT/'agent.yml'),'--out',str(models),'--fixed-model-name','symitar'],cwd=ROOT,env=environment,start_new_session=True)
            try:status=child.wait(timeout=180)
            except subprocess.TimeoutExpired:raise ValueError('training_deadline') from None
            if status:raise ValueError('training_failed')
            archive=models/'symitar.tar.gz'
            if not archive.is_file():raise ValueError('trained_model_missing')
            prepare_runtime(run,origin,text_api=args.text_api)
            print('Mode: fictional local mock, four vendor input hashes verified. Routing identity is a simulator, not bank authentication.')
            print('Speak only fictional data. Request-level speech opt-out is enabled; it is not zero retention.')
            print('Inspector URL: '+url,flush=True)
            print('To stop every owned service: Ctrl+C in this terminal. Then stop the Codespace.',flush=True)
            child=subprocess.Popen([sys.executable,'-m','rasa','run' if args.text_api else 'inspect','--interface','127.0.0.1','--port',str(args.port),'--model',str(archive)],cwd=run,env=environment,start_new_session=True)
            while child.poll() is None:
                if any(not thread.is_alive() for thread in threads):raise ValueError('owned_server_exited')
                time.sleep(.1)
            return child.returncode
    except KeyboardInterrupt:return 0
    except Exception:
        print('Not ready. An owned service or fixture recovery failed. State is preserved; no raw service error or secret is printed.');return 1
    finally:
        failed=cleanup(child,servers,threads,state,journal,previous)
        if failed:
            print('Not ready. Owned cleanup incomplete ('+', '.join(failed)+'); preserve state and stop the Codespace.')
            return 1
