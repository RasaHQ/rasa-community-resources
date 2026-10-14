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
from rasa.mantle.state.tracker_handle import make_tracker_handle
from fixture_decisions import Decisions



def tool_records(tracker):
    records = []
    for event in tracker.events:
        item = event.as_dict()
        if item['event'] != 'tool_executed':
            continue
        if item.get('tool_name') == 'record_local_canary':
            if item.get('is_error'):
                raise AssertionError('Native recording tool execution failed')
            records.append(json.loads(item['result']))
    return records


class PairedTurnLoop(unittest.TestCase):
    async def send_message(self, agent, text, output, sender):
        await agent.handle_message(UserMessage(text, output, sender_id=sender))

    async def close_transport(self):
        pass

    def test_real_runtime_holds_the_scripted_write_until_a_later_user_turn(self):
        self.check_scenario('approve')

    def test_same_turn_self_confirmation_stays_pending_in_real_runtime(self):
        self.check_scenario('same-turn')

    def test_later_scripted_denial_cancels_in_real_runtime(self):
        self.check_scenario('deny')

    def test_no_followed_by_scripted_true_executes_as_a_labelled_limit(self):
        self.check_scenario('mismatched-denial')

    def check_scenario(self, scenario):
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
                    for variant in (('gated', 'ungated') if scenario == 'approve' else ('gated',)):
                        asyncio.run(self.run_variant(root, variant, port, scenario))
                finally:
                    child.terminate()
                    child.wait(timeout=10)

    async def run_variant(self, root, variant, port, scenario='approve'):
        source = root / variant
        prepare(variant, source, port, scripted_model_port=8938 if port != 8938 else 8939)
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
        decisions = Decisions(confirmed=scenario != 'deny',
                              attempt_same_turn=scenario == 'same-turn')

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
                failures = [event.as_dict() for event in tracker.events
                            if event.as_dict().get('event') == 'tool_executed'
                            and event.as_dict().get('is_error')]
                if scenario == 'same-turn':
                    self.assertEqual(len(failures), 1)
                    self.assertEqual(failures[0]['tool_name'], 'resolve_tool_confirmation')
                    self.assertIn('same turn', failures[0]['result'])
                else:
                    self.assertEqual(failures, [])
                self.assertTrue(decisions.saw_description)
                self.assertTrue(decisions.saw_result)
                self.assertEqual(len(first), 1)
                if variant == 'gated':
                    self.assertEqual(first[0]['status'], 'awaiting_confirmation')
                    if scenario == 'same-turn':
                        self.assertTrue(decisions.resolved, 'The script must actually attempt resolution')
                        handle = make_tracker_handle(tracker, agent.processor.mantle_static_data)
                        self.assertIsNotNone(handle.pending_tool_confirmation_for_active_frame())
                        self.assertFalse(any(r.get('status') == 'simulated_recording' for r in first))
                        self.assertEqual(decisions.failures, [])
                        return
                    self.assertTrue(any(message.get('text') ==
                        'Would you like me to record that fictional value?'
                        for message in output.messages))
                    decisions.phase = 'confirm'
                    message = 'No, do not record it.' if scenario in {'deny', 'mismatched-denial'} else 'Yes, record it.'
                    await self.send_message(agent, message, output, variant)
                    tracker = await agent.tracker_store.retrieve(variant)
                    records = tool_records(tracker)
                    self.assertFalse(any(event.as_dict().get('is_error')
                                         for event in tracker.events
                                         if event.as_dict().get('event') == 'tool_executed'))
                    self.assertEqual(len(records), 2)
                    self.assertTrue(decisions.resolved)
                    if scenario == 'deny':
                        self.assertFalse(any(r.get('status') == 'simulated_recording' for r in records))
                        handle = make_tracker_handle(tracker, agent.processor.mantle_static_data)
                        self.assertIsNone(handle.pending_tool_confirmation_for_active_frame())
                        self.assertEqual(records[1]['status'], 'declined')
                    else:
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
