"""Actual archived Mantle turn loops with MCP and a scripted model boundary.

The script deliberately requests a write without caller approval. It measures
engine enforcement only, not model susceptibility or interpretation of consent.
No gate, invoker, tracker or MCP result is replaced.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from mock_server import CANARY, DESCRIPTION
from prepare import prepare
from rasa.core.agent import Agent
from rasa.core.channels.channel import CollectingOutputChannel, UserMessage
from rasa.core.config.configuration import Configuration
from rasa.mantle.llm.client import LLMClient
from rasa.mantle.model_archive.snapshot import package_model_archive
from rasa.shared.providers.llm.llm_response import LLMResponse, LLMToolCall


class Decisions:
    def __init__(self):
        self.stage = 0
        self.phase = 'read'
        self.resolved = False
        self.failures = []
        self.saw_description = False
        self.saw_result = False

    async def complete(self, client, messages, tools=None, model_settings=None):
        try:
            schemas = {item['function']['name']: item['function'] for item in tools or []}
            if set(schemas) == {'record_discovered_facts'}:
                return self.response('record_discovered_facts', {'facts': []})
            if not tools:
                return self.response(text='Please confirm the fictional recording.')
            if self.stage == 0:
                assert 'review_case' in schemas['activate']['parameters']['properties']['target_id']['enum']
                result = self.response('activate', {'target_id': 'review_case'})
            elif self.stage == 1:
                assert schemas['read_case']['description'] == DESCRIPTION
                self.saw_description = True
                result = self.response('read_case', {})
            elif self.stage == 2:
                assert CANARY in str(messages)
                self.saw_result = True
                result = self.response('record_local_canary', {'value': CANARY})
            elif self.phase == 'confirm' and not self.resolved:
                assert 'resolve_tool_confirmation' in schemas
                self.resolved = True
                result = self.response('resolve_tool_confirmation', {'confirmed': True})
            elif self.phase == 'read' and 'resolve_tool_confirmation' in schemas:
                result = self.response(text='Would you like me to record that fictional value?')
            else:
                result = self.response(text='Done with the fictional case.')
            if result.tool_calls:
                assert result.tool_calls[0].tool_name in schemas
            self.stage += 1
            return result
        except Exception as error:
            self.failures.append(str(error))
            raise

    def response(self, name=None, arguments=None, text=None):
        return LLMResponse(id=f'scripted-{self.stage}', choices=[text] if text else [],
            created=0, tool_calls=[LLMToolCall(id=f'call-{self.stage}',
                tool_name=name, tool_args=arguments or {})] if name else None)


def tool_records(tracker):
    records = []
    for event in tracker.events:
        item = event.as_dict()
        if item['event'] != 'tool_executed':
            continue
        if item.get('is_error'):
            raise AssertionError('Native tool execution failed')
        if item.get('tool_name') == 'record_local_canary':
            records.append(json.loads(item['result']))
    return records


class PairedTurnLoop(unittest.TestCase):
    async def send_message(self, agent, text, output, sender):
        await agent.handle_message(UserMessage(text, output, sender_id=sender))

    async def close_transport(self):
        pass

    def test_real_runtime_holds_the_scripted_write_until_a_later_user_turn(self):
        env = {'OPENAI_API_KEY': 'placeholder-not-a-real-key', 'RASA_LICENSE': '',
            'RASA_PRO_LICENSE': '', 'RASA_TELEMETRY_ENABLED': 'false',
            'PYTHON_DOTENV_DISABLED': 'true', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
            'LLM_API_HEALTH_CHECK': 'false', 'DO_NOT_TRACK': '1'}
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, env):
            root = Path(temp)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            with tempfile.TemporaryFile() as log:
                child = subprocess.Popen([sys.executable,
                    str(Path(__file__).with_name('mock_server.py')), '--port', str(port)],
                    stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 10
                    while True:
                        if child.poll() is not None:
                            raise AssertionError('Owned mock server failed to start')
                        try:
                            with socket.create_connection(('127.0.0.1', port), timeout=.2):
                                break
                        except OSError:
                            if time.monotonic() > deadline:
                                raise
                            time.sleep(.05)
                    for variant in ('gated', 'ungated'):
                        asyncio.run(self.run_variant(root, variant, port))
                finally:
                    child.terminate()
                    child.wait(timeout=10)

    async def run_variant(self, root, variant, port):
        source = root / variant
        prepare(variant, source, port)
        result = package_model_archive(str(source / 'agent.yml'), str(root / 'archives'),
            fixed_model_name=variant, validate=True)
        self.assertEqual(result.code, 0)
        live = root / f'live-{variant}'
        live.mkdir()
        # Model/provider configuration is intentionally separate from the archive.
        (live / 'integrations.yml').write_bytes((source / 'integrations.yml').read_bytes())
        source.rename(root / f'.retained-{variant}')
        self.assertFalse(source.exists())
        previous = Path.cwd()
        os.chdir(live)
        agent = None
        decisions = Decisions()

        async def complete(client, *args, **kwargs):
            return await decisions.complete(client, *args, **kwargs)

        async def streaming(*args, **kwargs):
            decisions.failures.append('Unexpected streaming boundary')
            raise AssertionError('Use the collecting text channel')

        try:
            Configuration.initialise_endpoints(None)
            agent = Agent.load(result.model)
            await agent.prepare_runtime_integrations()
            with patch.object(LLMClient, 'acompletion', complete), \
                    patch.object(LLMClient, 'acompletion_streaming', streaming):
                output = CollectingOutputChannel()
                await self.send_message(agent, 'Read my fictional support case.',
                    output, variant)
                tracker = await agent.tracker_store.retrieve(variant)
                first = tool_records(tracker)
                self.assertTrue(decisions.saw_description)
                self.assertTrue(decisions.saw_result)
                self.assertEqual(len(first), 1)
                if variant == 'gated':
                    self.assertEqual(first[0]['status'], 'awaiting_confirmation')
                    self.assertTrue(any(message.get('text') ==
                        'Would you like me to record that fictional value?'
                        for message in output.messages))
                    decisions.phase = 'confirm'
                    await self.send_message(agent, 'Yes, record it.', output, variant)
                    tracker = await agent.tracker_store.retrieve(variant)
                    records = tool_records(tracker)
                    self.assertEqual(len(records), 2)
                    self.assertTrue(decisions.resolved)
                    self.assertEqual(records[1], {'status': 'simulated_recording', 'value': CANARY})
                else:
                    self.assertEqual(first[0], {'status': 'simulated_recording', 'value': CANARY})
                self.assertEqual(decisions.failures, [])
        finally:
            await self.close_transport()
            if agent is not None:
                await agent.close()
            os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
