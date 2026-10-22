"""Launcher controls; no provider/voice call or independent acceptance claim.

sow: software-factories-masterclass-SOW-02
"""
import asyncio
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import demo_launcher as demo


class LauncherControls(unittest.TestCase):
    def setUp(self):
        (ROOT / '.demo-cache').mkdir(exist_ok=True)

    def test_registry_lock_accepts_actual_pypi_locks(self):
        for directory in (demo.WORKER, demo.PROJECT):
            demo.registry_lock(directory)

    def test_registry_lock_refuses_file_wheel_and_other_registry(self):
        for source in ('{ path = "../private.whl" }', '{ registry = "https://elsewhere.invalid/simple" }'):
            with tempfile.TemporaryDirectory(dir=ROOT / '.demo-cache') as name:
                directory = Path(name)
                (directory / 'pyproject.toml').write_text('[project]\ndependencies=["zeocore==1.0"]\n')
                (directory / 'uv.lock').write_text('[[package]]\nname="zeocore"\nversion="1.0"\nsource='+source+'\n')
                with self.assertRaises(demo.DemoError):
                    demo.registry_lock(directory)

    def test_setup_discovers_existing_python_before_redirected_runtime_data(self):
        results = [SimpleNamespace(returncode=0, stdout=sys.executable + '\n'), SimpleNamespace(returncode=0)]
        with patch.dict(os.environ, {'XDG_DATA_HOME': '/existing-python-data'}), \
                patch.object(demo.subprocess, 'run', side_effect=results) as run, \
                patch.object(demo, 'completed'), \
                patch.object(demo.shutil, 'which', return_value='/installed/uv'):
            demo.setup()
        self.assertEqual(run.call_args_list[0].kwargs['env']['XDG_DATA_HOME'], '/existing-python-data')
        self.assertIn('--no-python-downloads', run.call_args_list[0].args[0])
        self.assertNotEqual(demo.child_environment()['XDG_DATA_HOME'], '/existing-python-data')

    def test_missing_setup_has_fixed_error_no_traceback(self):
        output = io.StringIO()
        with patch.object(Path, 'is_file', return_value=False), redirect_stderr(output):
            self.assertEqual(demo.main(['run']), 1)
        self.assertIn('Run ./demo setup', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())

    def test_missing_license_refuses_before_any_process_or_service(self):
        output = io.StringIO()
        with patch.object(Path, 'is_file', return_value=True), \
                patch.object(demo, 'require_free_ports'), \
                patch.object(demo, 'child_environment', return_value={}), \
                patch.object(demo.Children, 'start') as start, redirect_stderr(output):
            self.assertEqual(demo.main(['run', '--scripted']), 1)
        self.assertIn('RASA_LICENSE', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())
        start.assert_not_called()

    def test_unknown_option_never_echoes_a_value(self):
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(demo.main(['--unknown-private-value']), 1)
        self.assertNotIn('private-value', output.getvalue())

    def test_busy_port_is_not_killed(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            real_socket = socket.socket
            class BusySocket:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def bind(self, address):
                    raise OSError('deliberate owned busy listener')
            with patch.object(demo.socket, 'socket', BusySocket):
                with self.assertRaises(demo.DemoError):
                    demo.require_free_ports()
            with real_socket() as client:
                client.connect(listener.getsockname())

    @unittest.skipUnless(os.name == 'posix', 'process group check needs POSIX')
    def test_close_stops_actual_grandchild_listener(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        code = (
            'import subprocess,sys,time; '
            'subprocess.Popen([sys.executable,"-m","http.server",'
            + repr(str(port)) + ',"--bind","127.0.0.1"]); time.sleep(120)'
        )
        children = demo.Children()
        try:
            children.start([sys.executable, '-c', code], cwd=ROOT, env=os.environ.copy())
            until = time.monotonic() + 5
            ready = False
            while time.monotonic() < until:
                with socket.socket() as client:
                    if client.connect_ex(('127.0.0.1', port)) == 0:
                        ready = True
                        break
                time.sleep(0.05)
            self.assertTrue(ready, 'actual owned grandchild did not start')
        finally:
            children.close()
        with socket.socket() as client:
            self.assertNotEqual(client.connect_ex(('127.0.0.1', port)), 0)

    def test_failed_voice_start_retries_text_once_without_stopping_source(self):
        first, second = object(), object()
        children = unittest.mock.Mock()
        children.start.side_effect = [first, second]
        environment = {'DEEPGRAM_API_KEY': 'synthetic-test-only', 'BRIEFING_MCP_TOKEN': 'synthetic-private-token'}
        with patch.object(demo, 'wait_http', side_effect=[demo.DemoError('fixed test failure'), None]):
            process, text_env = demo.start_inspector(children, environment, 'live')
        self.assertIs(process, second)
        children.stop.assert_called_once_with(first)
        self.assertNotIn('DEEPGRAM_API_KEY', text_env)
        self.assertEqual(text_env['BRIEFING_MCP_TOKEN'], 'synthetic-private-token')
        self.assertIn('DEEPGRAM_API_KEY', environment)
        self.assertEqual(children.start.call_count, 2)
        self.assertNotIn('DEEPGRAM_API_KEY', children.start.call_args_list[1].kwargs['env'])

    def test_text_start_failure_does_not_loop_or_claim_voice_failure(self):
        children = unittest.mock.Mock()
        with patch.object(demo, 'wait_http', side_effect=demo.DemoError('fixed test failure')):
            with self.assertRaises(demo.DemoError):
                demo.start_inspector(children, {}, 'scripted')
        self.assertEqual(children.start.call_count, 1)
        children.stop.assert_not_called()

    def test_healthy_voice_start_keeps_same_actual_inspector(self):
        children = unittest.mock.Mock()
        environment = {'DEEPGRAM_API_KEY': 'synthetic-test-only'}
        with patch.object(demo, 'wait_http'):
            process, result = demo.start_inspector(children, environment, 'live')
        self.assertIs(process, children.start.return_value)
        self.assertIs(result, environment)
        children.stop.assert_not_called()
        self.assertEqual(children.start.call_count, 1)

    def test_tool_record_only_decodes_structured_result(self):
        value = {'briefing_id': 'synthetic-private-capability', 'status': 'started'}
        wrapped = [{'type': 'text', 'text': json.dumps(value)}]
        self.assertEqual(demo.tool_record(wrapped), value)
        self.assertIsNone(demo.tool_record('not a JSON object'))


class ScriptedRouting(unittest.IsolatedAsyncioTestCase):
    async def call(self, messages, names):
        return await demo.ScriptedClient().acompletion(messages, tools=[{'function': {'name': name}} for name in names])

    async def test_scripted_activates_real_skill_tool(self):
        reply = await self.call([{'role': 'user', 'content': 'weather'}], ['activate'])
        self.assertEqual(reply.tool_calls[0].tool_name, 'activate')
        self.assertEqual(reply.tool_calls[0].tool_args, {'target_id': 'briefing'})

    async def test_scripted_start_preserves_explicit_inputs(self):
        text = 'callsign=TEST123 meeting=2026-10-22T21:00:00Z transfer=45'
        reply = await self.call([{'role': 'user', 'content': text}], ['briefing'])
        self.assertEqual(reply.tool_calls[0].tool_args, {'action': 'start', 'request': text})

    async def test_scripted_get_uses_actual_tool_capability(self):
        reply = await self.call([
            {'role': 'user', 'content': 'weather'},
            {'role': 'tool', 'content': json.dumps({'briefing_id': 'test-only-capability', 'status': 'started'})},
        ], ['briefing'])
        self.assertEqual(reply.tool_calls[0].tool_args, {'action': 'get', 'briefing_id': 'test-only-capability'})

    async def test_revision_reuses_same_capability_not_a_new_start(self):
        reply = await self.call([
            {'role': 'tool', 'content': json.dumps({'briefing_id': 'test-only-capability', 'status': 'complete'})},
            {'role': 'user', 'content': 'transfer=60'},
        ], ['briefing'])
        self.assertEqual(reply.tool_calls[0].tool_args, {'action': 'revise', 'briefing_id': 'test-only-capability', 'change': 'transfer=60'})

    async def test_completed_source_result_stops_tool_loop_without_model_numbers(self):
        reply = await self.call([
            {'role': 'user', 'content': 'weather'},
            {'role': 'tool', 'content': json.dumps({'briefing_id': 'test-only-capability', 'status': 'complete', 'cards': []})},
        ], ['briefing'])
        self.assertFalse(reply.tool_calls)
        self.assertIn('SCRIPTED', reply.response_text())
        self.assertNotIn('test-only-capability', reply.response_text())


class ActualMCPResponseShapes(unittest.IsolatedAsyncioTestCase):
    async def test_terminal_get_without_repeated_capability_stops_the_loop(self):
        client = demo.ScriptedClient()
        response = await client.acompletion([
            {'role': 'user', 'content': 'callsign=TEST123'},
            {'role': 'tool', 'content': json.dumps({'briefing_id': 'actual-start-capability', 'status': 'started'})},
            {'role': 'tool', 'content': json.dumps({'status': 'incomplete', 'cards': [], 'reason': 'source unavailable'})},
        ], tools=[{'function': {'name': 'briefing'}}])
        self.assertFalse(response.tool_calls)
        self.assertIn('validated source cards', response.response_text())

    async def test_running_get_reuses_the_capability_from_start(self):
        response = await demo.ScriptedClient().acompletion([
            {'role': 'user', 'content': 'callsign=TEST123'},
            {'role': 'tool', 'content': json.dumps({'briefing_id': 'actual-start-capability', 'status': 'started'})},
            {'role': 'tool', 'content': json.dumps({'status': 'running', 'progress': ['Checking sources']})},
        ], tools=[{'function': {'name': 'briefing'}}])
        self.assertEqual(response.tool_calls[0].tool_args,
                         {'action': 'get', 'briefing_id': 'actual-start-capability'})

    async def test_status_after_terminal_get_does_not_launch_another_source_read(self):
        response = await demo.ScriptedClient().acompletion([
            {'role': 'tool', 'content': json.dumps({'briefing_id': 'actual-start-capability', 'status': 'started'})},
            {'role': 'tool', 'content': json.dumps({'status': 'complete', 'cards': []})},
            {'role': 'user', 'content': 'status'},
        ], tools=[{'function': {'name': 'briefing'}}])
        self.assertEqual(response.tool_calls[0].tool_args,
                         {'action': 'get', 'briefing_id': 'actual-start-capability'})


class MantleVoiceConfig(unittest.TestCase):
    def test_real_mantle_parser_accepts_flux_aura_without_enabled_keyword(self):
        voice = {'inspector': {'enabled': True,
            'asr': {'name': 'deepgram', 'language_map': {'en': {'model': 'flux-general-en'}}},
            'tts': {'name': 'deepgram', 'language_map': {'en': {'model': 'aura-2-andromeda-en'}}}}}
        result = demo.merge_voice_channels({'rest': {}}, voice)
        self.assertEqual(result['inspector']['asr'], voice['inspector']['asr'])
        self.assertEqual(result['inspector']['tts'], voice['inspector']['tts'])
        self.assertNotIn('enabled', result['inspector'])
        self.assertIn('rest', result)
        self.assertIn('enabled', voice['inspector'])


if __name__ == '__main__':
    unittest.main()
