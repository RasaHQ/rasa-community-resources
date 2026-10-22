"""Offline A6 control through the released run_native adapter and the real factory.

sow: software-factories-masterclass-SOW-02
The SDK-shaped stream supplies a labelled teaching action, not model-generated code.
There is no OpenAI client, API key read or network request.
"""
import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('factory_native_driver', HERE / 'openai_factory_driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class ScriptedStream:
    def __init__(self, handlers, actions):
        self.handlers, self.actions = handlers, actions

    def with_result_collection(self):
        return self

    def __iter__(self):
        yield {'type': 'agent.session.turn.created', 'turn': {'id': 'scripted-factory-turn'}}
        for action in self.actions:
            result = self.handlers['write_file'](action)
            if not result.get('ok'):
                raise ValueError('scripted_action_refused')
            yield {'type': 'scripted.file_action.completed'}
        yield {'type': 'agent.session.turn.completed', 'turn_id': 'scripted-factory-turn'}
        yield {'type': 'agent.session.idle'}
        raise AssertionError('The native adapter read beyond the completed turn boundary')

    def get_final_result(self):
        return SimpleNamespace(session_id='scripted-no-provider-session', output_text='SCRIPTED teaching change completed.')

    def close(self):
        pass


class ScriptedSessions:
    def __init__(self, actions):
        self.actions = actions
        self.calls = 0

    def create(self, *, agent, environment, input, stream, tool_handlers, timeout, spend_control):
        self.calls += 1
        if (environment != {'type': 'none'} or stream is not True or timeout != 20
                or spend_control != {'limit': 200}):
            raise ValueError('native_request_contract_changed')
        if {tool['name'] for tool in agent['tools']} != {'list_files', 'read_file', 'write_file'}:
            raise ValueError('unexpected_native_tools')
        if 'acceptance' in json.loads(input):
            raise ValueError('protected_task_data_exposed')
        return ScriptedStream(tool_handlers, self.actions)


def qualify(pack, evidence):
    pack, evidence = Path(pack).resolve(), Path(evidence).resolve()
    if evidence.exists():
        raise ValueError('fresh_evidence_directory_required')
    evidence.mkdir(parents=True)
    task = pack / 'tasks/a6-market-watchlist.json'
    workspace = evidence / 'scratch'
    driver.module('scratch').main(task, workspace, pack_root=pack, instructions='AGENTS-a6.md')
    teaching = pack / 'candidates/market-good'
    actions = [{'path': str(path.relative_to(teaching)), 'text': path.read_text()}
               for path in driver.module('factory').files_in(teaching)]
    sessions = ScriptedSessions(actions)
    client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=sessions)))
    code = driver.execute(task, workspace, evidence / 'run', client=client,
                          model='SCRIPTED-no-model-request', pack_root=pack,
                          environment_path=driver.FACTORY / 'environment-a6.json', spend_limit_cents=200, mode='SCRIPTED')
    (evidence / 'scripted-control.json').write_text(json.dumps({
        'mode': 'SCRIPTED SDK-shaped stream through actual Core run_native',
        'model_generated_code': False, 'provider_calls': 0,
        'native_adapter_invocations': sessions.calls, 'factory_exit_code': code,
        'integration': 'NOT RUN: receiving product hook required'}, indent=2) + '\n')
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack_root')
    parser.add_argument('new_evidence_directory')
    args = parser.parse_args(argv)
    try:
        code = qualify(args.pack_root, args.new_evidence_directory)
        print('SCRIPTED native-to-factory control exit: ' + str(code) + '; no provider call or product integration claimed.')
        return code
    except Exception:
        print('The scripted control could not run; use the reviewed Core native worker and a fresh evidence directory.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
