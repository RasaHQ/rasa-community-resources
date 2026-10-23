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
                patch('demo_make.mark_environment'), \
                patch.object(demo, 'participant_environment', side_effect=lambda env: dict(env)), \
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
                def setsockopt(self, *args):
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


    def test_opt_in_child_diagnostics_redact_before_writing(self):
        import secrets
        values = {name: secrets.token_urlsafe(32) for name in (
            'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPGRAM_API_KEY', 'RASA_LICENSE', 'BRIEFING_MCP_TOKEN')}
        with tempfile.TemporaryDirectory(dir=ROOT / '.demo-cache') as directory:
            env = {**os.environ, **values, 'BRIEFING_DIAGNOSTICS_DIR': directory}
            code = 'import os; [print(os.environ[k], os.environ[k][3:11]) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPGRAM_API_KEY", "RASA_LICENSE", "BRIEFING_MCP_TOKEN")]'
            children = demo.Children()
            try:
                with patch.dict(os.environ, {key: "" for key in values}):
                    process = children.start([sys.executable, '-c', code], cwd=ROOT, env=env)
                    self.assertEqual(process.wait(timeout=5), 0)
                    for thread in children.log_threads:
                        thread.join(timeout=5)
                    output = ''.join(path.read_text() for path in Path(directory).glob('*.log'))
                self.assertIn('redacted', output)
                for value in values.values():
                    self.assertNotIn(value, output)
                    for index in range(len(value) - 7):
                        self.assertNotIn(value[index:index + 8], output)
            finally:
                children.close()


    def test_native_source_model_is_supported_session_default_and_scripted_never_calls_it(self):
        environment = {'OPENAI_API_KEY': 'synthetic-ready-key-only'}
        self.assertTrue(demo.configure_native_sources(environment, False))
        self.assertEqual(environment['BRIEFING_AGENTS_MODEL'], 'gpt-6-astra')
        override = {**environment, 'BRIEFING_AGENTS_MODEL': 'explicit-native-model'}
        self.assertTrue(demo.configure_native_sources(override, False))
        self.assertEqual(override['BRIEFING_AGENTS_MODEL'], 'explicit-native-model')
        self.assertFalse(demo.configure_native_sources(environment, True))
        self.assertFalse(demo.configure_native_sources({}, False))


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

    async def test_ambiguous_airports_reach_backend_without_inventing_destination(self):
        text = 'JFK or Newark'
        initial = await self.call([{'role': 'user', 'content': text}], ['briefing', 'find_flights'])
        self.assertEqual(initial.tool_calls[0].tool_args, {'action': 'start', 'request': text})
        previous = [{'role': 'tool', 'content': json.dumps({'briefing_id': 'synthetic-owner-job', 'status': 'needs_input'})}]
        followup = await self.call(previous + [{'role': 'user', 'content': text}], ['briefing', 'find_flights'])
        self.assertEqual(followup.tool_calls[0].tool_args,
            {'action': 'revise', 'briefing_id': 'synthetic-owner-job', 'change': text})
        resumed = await self.call(previous + [{'role': 'user', 'content': 'Newark'}], ['briefing'])
        self.assertEqual(resumed.tool_calls[0].tool_args,
            {'action': 'revise', 'briefing_id': 'synthetic-owner-job', 'change': 'Newark'})

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


    async def test_scripted_unknown_flight_uses_actual_finder_tool(self):
        text = "I am heading to New York. Which flights are already in the air?"
        response = await self.call([{'role': 'user', 'content': text}], ['briefing', 'find_flights'])
        self.assertEqual(response.tool_calls[0].tool_name, 'find_flights')
        self.assertEqual(response.tool_calls[0].tool_args, {'destination': text})

    async def test_uncovered_discovery_result_ends_tool_loop(self):
        response = await self.call([{'role': 'user', 'content': 'no'},
            {'role': 'tool', 'content': json.dumps({'status': 'unsupported_destination',
                'candidates': [], 'message': 'Published routes cover New York only.'})}], ['briefing', 'find_flights'])
        self.assertFalse(response.tool_calls)

    async def test_repeated_negative_after_uncovered_search_does_not_search_or_ask_again(self):
        response = await self.call([{'role': 'user', 'content': 'flight to London tonight'},
            {'role': 'tool', 'content': json.dumps({'status': 'unsupported_destination', 'candidates': [],
                'message': 'Published routes cover New York only.'})},
            {'role': 'user', 'content': 'no'}], ['briefing', 'find_flights'])
        self.assertFalse(response.tool_calls)
        self.assertIn("don't need to answer", response.response_text())
        self.assertNotIn('?', response.response_text())

    @staticmethod
    def suggested_search():
        return {'status': 'found', 'discovery_id': 'brf_synthetic_suggested', 'partial': False,
            'source_date': '2026-10-22', 'candidates': [dict(choice=n, callsign=call,
                origin='EDDF', destination='KJFK', altitude_feet=25000,
                position_age_seconds=5, landing_estimate_minutes=minutes)
                for n, call, minutes in [(1, 'DLH400', 35), (2, 'UAL57', 10)]]}

    async def test_short_confirmation_selects_only_the_announced_suggestion(self):
        from briefing.traveller import discovery_notice
        search = self.suggested_search()
        notice = discovery_notice(search)
        self.assertIn('My suggestion is United Airlines 57', notice)
        self.assertIn('soonest', notice)
        for answer in ('yes', 'that one', 'yes that one', 'yes, that one', 'Yes, that one.', 'Yes. That', 'yeah', 'that is the one', 'yes please'):
            response = await self.call([{'role': 'tool', 'content': json.dumps(search)},
                {'role': 'assistant', 'content': notice}, {'role': 'user', 'content': answer}], ['briefing', 'find_flights'])
            self.assertEqual(response.tool_calls[0].tool_args,
                {'action': 'start', 'request': answer, 'discovery_id': search['discovery_id'], 'choice': 2})

    async def test_spoken_confirmation_rejects_negatives_and_number_overrides(self):
        search = self.suggested_search()
        for answer in ('yes no', 'that is not mine', 'yeah no United 57',
                       'yes second one', 'that flight 3', 'yes two', 'yes one',
                       "that isn't the one", "that one isn't right",
                       "yeah, I'd prefer another", "that's too early", 'yes but cheaper'):
            response = await self.call([{'role': 'tool', 'content': json.dumps(search)},
                {'role': 'user', 'content': answer}], ['briefing', 'find_flights'])
            self.assertFalse(response.tool_calls, answer)

    async def test_explicit_choice_overrides_suggestion_and_decline_does_not_select(self):
        search = self.suggested_search()
        for answer, expected in [('the first one', 1), ('Lufthansa 400', 1), ('United 57', 2)]:
            response = await self.call([{'role': 'tool', 'content': json.dumps(search)},
                {'role': 'user', 'content': answer}], ['briefing', 'find_flights'])
            self.assertEqual(response.tool_calls[0].tool_args['choice'], expected)
        history = [{'role': 'tool', 'content': json.dumps(search)}]
        first = await self.call(history + [{'role': 'user', 'content': 'no'}], ['briefing', 'find_flights'])
        self.assertFalse(first.tool_calls)
        self.assertIn('Which flight', first.response_text())
        history += [{'role': 'user', 'content': 'no'}, {'role': 'assistant', 'content': first.response_text()}]
        for answer in ('no', 'yes', 'that one', 'yes, that one', 'Yes, that one.', 'Yes. That', 'yeah'):
            followup = await self.call(history + [{'role': 'user', 'content': answer}], ['briefing', 'find_flights'])
            self.assertFalse(followup.tool_calls)
            self.assertNotIn('?', followup.response_text())
            self.assertNotEqual(followup.response_text(), first.response_text())

    async def test_negative_nonflight_answers_preserve_selected_journey(self):
        for field in ('meeting_time', 'transfer_minutes'):
            for answer in ('no', 'not sure', 'no idea', "I don't know"):
                messages = [{'role': 'user', 'content': 'flight to New York tonight'},
                    {'role': 'tool', 'content': json.dumps({'status': 'needs_input',
                        'briefing_id': 'synthetic-old-opening', 'needs_input': {'field': 'flight'}})},
                    {'role': 'user', 'content': 'the first one'},
                    {'role': 'tool', 'content': json.dumps({'status': 'needs_input',
                        'briefing_id': 'synthetic-selected-journey', 'needs_input': {'field': field}})},
                    {'role': 'user', 'content': answer}]
                response = await self.call(messages, ['briefing', 'find_flights'])
                self.assertEqual(response.tool_calls[0].tool_name, 'briefing')
                self.assertEqual(response.tool_calls[0].tool_args,
                    {'action': 'revise', 'briefing_id': 'synthetic-selected-journey', 'change': answer})

    async def test_negative_flight_answers_reuse_last_stated_destination(self):
        for destination in ('London', 'New York', 'Reykjavik'):
            for answer in ('no', "no, i don't know", 'no idea', 'not sure', 'I do not know'):
                messages = [{'role': 'user', 'content': 'flight to ' + destination + ' tonight'},
                    {'role': 'tool', 'content': json.dumps({'status': 'needs_input', 'briefing_id': 'synthetic-owner',
                        'needs_input': {'field': 'flight'}})}, {'role': 'user', 'content': answer}]
                response = await self.call(messages, ['briefing', 'find_flights'])
                self.assertEqual(response.tool_calls[0].tool_name, 'find_flights')
                self.assertEqual(response.tool_calls[0].tool_args, {'destination': destination})

    async def test_negative_answer_does_not_resurrect_destination_before_ambiguity(self):
        response = await self.call([{'role': 'user', 'content': 'New York'},
            {'role': 'user', 'content': 'JFK or Newark'},
            {'role': 'user', 'content': 'no'}], ['briefing', 'find_flights'])
        self.assertNotEqual(response.tool_calls[0].tool_name, 'find_flights')

    async def test_scripted_choice_uses_only_returned_discovery_and_valid_index(self):
        previous = {'status': 'found', 'discovery_id': 'brf_synthetic_discovery', 'candidates': [{}, {}]}
        for choice, expected in [('the second one', 2), ('1', 1)]:
            response = await self.call([{'role': 'tool', 'content': json.dumps(previous)},
                {'role': 'user', 'content': choice}], ['briefing', 'find_flights'])
            self.assertEqual(response.tool_calls[0].tool_args, {'action': 'start', 'request': choice,
                'discovery_id': previous['discovery_id'], 'choice': expected})
        for answer in ['the fifth one', 'yes', 'invented flight']:
            response = await self.call([{'role': 'tool', 'content': json.dumps(previous)},
                {'role': 'user', 'content': answer}], ['briefing', 'find_flights'])
            self.assertFalse(response.tool_calls)
            self.assertIn('Which flight', response.response_text())

    async def test_new_discovery_choice_supersedes_the_empty_opening_briefing(self):
        # The real Inspector starts an empty briefing to ask its opening question.
        # Its older capability must not turn a subsequent flight choice into a
        # revision of that empty job. These are actual tracker JSON result shapes.
        messages = [
            {'role': 'tool', 'content': json.dumps({'status': 'started', 'briefing_id': 'synthetic-empty-opening'})},
            {'role': 'tool', 'content': json.dumps({'status': 'needs_input', 'needs_input': {'field': 'destination'}})},
            {'role': 'user', 'content': 'Which flights are in the air heading to New York?'},
            {'role': 'tool', 'content': json.dumps({'status': 'found', 'discovery_id': 'synthetic-new-search', 'candidates': [{}, {}]})},
            {'role': 'user', 'content': 'the second one'},
        ]
        response = await self.call(messages, ['briefing', 'find_flights'])
        self.assertEqual(response.tool_calls[0].tool_args, {'action': 'start',
            'request': 'the second one', 'discovery_id': 'synthetic-new-search', 'choice': 2})
        # Once that selection starts its own job, later answers revise it.
        messages.extend([
            {'role': 'tool', 'content': json.dumps({'status': 'started', 'briefing_id': 'synthetic-selected-flight'})},
            {'role': 'tool', 'content': json.dumps({'status': 'needs_input', 'needs_input': {'field': 'meeting_time'}})},
            {'role': 'user', 'content': 'the 6 pm meeting tomorrow'},
        ])
        response = await self.call(messages, ['briefing', 'find_flights'])
        self.assertEqual(response.tool_calls[0].tool_args, {'action': 'revise',
            'briefing_id': 'synthetic-selected-flight', 'change': 'the 6 pm meeting tomorrow'})

    async def test_failed_partial_or_empty_search_cannot_replace_the_selected_job(self):
        for bad in [
            {'status': 'unavailable', 'candidates': []},
            {'status': 'found', 'partial': True, 'discovery_id': 'synthetic-partial', 'candidates': [{}]},
            {'status': 'found', 'discovery_id': 'synthetic-empty', 'candidates': []},
        ]:
            messages = [
                {'role': 'tool', 'content': json.dumps({'status': 'complete', 'briefing_id': 'synthetic-selected'})},
                {'role': 'tool', 'content': json.dumps(bad)},
                {'role': 'user', 'content': 'the 6 pm meeting tomorrow'},
            ]
            with self.subTest(search=bad['status'], partial=bad.get('partial')):
                response = await self.call(messages, ['briefing', 'find_flights'])
                self.assertEqual(response.tool_calls[0].tool_args, {'action': 'revise',
                    'briefing_id': 'synthetic-selected', 'change': 'the 6 pm meeting tomorrow'})

    async def test_later_failed_search_never_reuses_an_older_choice_list(self):
        messages = [
            {'role': 'tool', 'content': json.dumps({'status': 'found', 'discovery_id': 'synthetic-old', 'candidates': [{}]})},
            {'role': 'tool', 'content': json.dumps({'status': 'no_results', 'candidates': []})},
            {'role': 'user', 'content': 'the first one'},
        ]
        response = await self.call(messages, ['briefing', 'find_flights'])
        self.assertNotIn('discovery_id', response.tool_calls[0].tool_args)

    async def test_scripted_new_turns_do_not_exhaust_a_lifetime_call_counter(self):
        client = demo.ScriptedClient()
        for _ in range(15):
            result = await client.acompletion([{'role': 'user', 'content': 'Lufthansa 400 to JFK'}],
                tools=[{'function': {'name': 'briefing'}}])
            self.assertEqual(result.tool_calls[0].tool_args['action'], 'start')


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


class InspectorVoiceSeam(unittest.TestCase):
    def setUp(self):
        (ROOT / '.demo-cache').mkdir(exist_ok=True)

    def test_real_channel_resolver_sees_patch_even_when_imported_first(self):
        from rasa.core.config.channel_loading import resolve_channels_config
        from rasa.mantle.config import channels
        voice = {'inspector': {'enabled': True,
            'asr': {'name': 'deepgram', 'language_map': {'en': {'model': 'flux-general-en'}}},
            'tts': {'name': 'deepgram', 'language_map': {'en': {'model': 'aura-2-andromeda-en'}}}}}
        with tempfile.TemporaryDirectory(dir=ROOT / '.demo-cache') as directory:
            root = Path(directory)
            (root / 'integrations.yml').write_text('channels:\n  rest: {}\n')
            skill = root / 'skills' / 'briefing'
            skill.mkdir(parents=True)
            (skill / 'skill.md').write_text('# Briefing\n')
            with patch.object(channels, 'load_integration_channels', channels.load_integration_channels):
                demo.install_voice_channels(voice)
                config = resolve_channels_config(project_root=root)
            inspector = config.channels['inspector']
            self.assertEqual(inspector['asr']['name'], 'deepgram')
            self.assertEqual(inspector['asr']['language_map']['en']['model'], 'flux-general-en')
            self.assertEqual(inspector['tts']['name'], 'deepgram')
            self.assertEqual(inspector['tts']['language_map']['en']['model'], 'aura-2-andromeda-en')
            self.assertNotIn('enabled', inspector)
            self.assertIn('rest', config.channels)
            self.assertEqual(config.config_file_path, root / 'integrations.yml')



@unittest.skipUnless(__import__('importlib').util.find_spec('rasa'), 'Mantle project interpreter required')
class ActualVoiceLoaderSeam(unittest.TestCase):
    def test_actual_channel_building_observes_inspector_runtime_patch(self):
        from rasa.core.agent import Agent
        from rasa.core.config.channel_loading import resolve_channels_config
        from rasa.mantle.config import channels
        from rasa.mantle.llm.client import LLMClient
        observed = []
        def normal_entrypoint():
            observed.append(resolve_channels_config(project_root=demo.PROJECT))
        original = channels.load_integration_channels
        with patch.object(channels, 'load_integration_channels', original), \
                patch.object(LLMClient, 'from_bootstrap'), \
                patch('rasa.__main__.main', side_effect=normal_entrypoint), \
                patch.object(sys, 'argv', []), \
                patch.dict(os.environ, {'DEEPGRAM_API_KEY': 'synthetic-voice-config-only', 'BRIEFING_MCP_TOKEN': 'synthetic-voice-loader-token-only', 'LITELLM_MODE': 'PRODUCTION'}, clear=True):
            demo.inspector('scripted')
        self.assertEqual(len(observed), 1)
        actual = observed[0].channels['inspector']
        self.assertEqual(actual['asr']['name'], 'deepgram')
        self.assertEqual(actual['asr']['language_map']['en']['model'], 'flux-general-en')
        self.assertEqual(actual['tts']['name'], 'deepgram')
        self.assertEqual(actual['tts']['language_map']['en']['model'], 'aura-2-andromeda-en')
        self.assertNotIn('synthetic-voice-config-only', json.dumps(actual))

    def test_actual_channel_building_is_keyless_without_expanding_other_integrations(self):
        from rasa.core.agent import Agent
        from rasa.core.config.channel_loading import resolve_channels_config
        from rasa.mantle.config import channels
        from rasa.mantle.llm.client import LLMClient
        observed = []
        def normal_entrypoint():
            observed.append(resolve_channels_config(project_root=demo.PROJECT))
        original = channels.load_integration_channels
        with patch.object(channels, 'load_integration_channels', original), \
                patch.object(LLMClient, 'from_bootstrap'), \
                patch('rasa.__main__.main', side_effect=normal_entrypoint), \
                patch.object(sys, 'argv', []), \
                patch.dict(os.environ, {'LITELLM_MODE': 'PRODUCTION'}, clear=True):
            demo.inspector('scripted')
        self.assertEqual(observed[0].channels, {})


class InspectorReadinessBudget(unittest.TestCase):
    def test_healthy_voice_gets_at_least_the_text_engine_readiness_budget(self):
        children = unittest.mock.Mock()
        with patch.object(demo, 'wait_http') as voice_wait:
            demo.start_inspector(children, {'DEEPGRAM_API_KEY': 'synthetic-test-only'}, 'scripted')
        with patch.object(demo, 'wait_http') as text_wait:
            demo.start_inspector(children, {}, 'scripted')
        voice_budget = voice_wait.call_args.kwargs['timeout']
        text_budget = text_wait.call_args.kwargs['timeout']
        self.assertGreaterEqual(voice_budget, text_budget)
        self.assertGreaterEqual(voice_budget, 90)


class ParticipantDotenv(unittest.TestCase):
    def setUp(self):
        (ROOT / '.demo-cache').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / '.demo-cache')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / 'project'
        self.worker = self.root / 'worker'
        self.project.mkdir()
        self.worker.mkdir()
        demo.subprocess.run(['git', 'init', '-q', str(self.root)], check=True,
                            stdout=demo.subprocess.DEVNULL, stderr=demo.subprocess.DEVNULL)
        (self.root / '.gitignore').write_text('.env\n')
        self.path = self.root / '.env'
        self.synthetic = 'fixture-only-do-not-echo-43b02a'

    def load(self, environment=None):
        return demo.participant_environment({} if environment is None else environment,
                                            self.root, self.project, self.worker)

    def test_four_names_literal_values_comments_and_quotes(self):
        self.path.write_text('\ufeff# Own values only\nRASA_LICENSE=fixture-licence\n'
                             'OPENAI_API_KEY="literal-${DO_NOT_EXPAND}-#-value"\n'
                             "ANTHROPIC_API_KEY='fixture-anthropic'\nDEEPGRAM_API_KEY=\n")
        result = self.load()
        self.assertEqual(set(result), demo.PARTICIPANT_KEYS)
        self.assertEqual(result['OPENAI_API_KEY'], 'literal-${DO_NOT_EXPAND}-#-value')
        self.assertEqual(result['ANTHROPIC_API_KEY'], 'fixture-anthropic')
        self.assertEqual(result['DEEPGRAM_API_KEY'], '')

    def test_nonempty_shell_wins_and_empty_uses_file_without_mutation(self):
        self.path.write_text('RASA_LICENSE=file-only\nOPENAI_API_KEY=file-only\n')
        original = {'RASA_LICENSE': 'shell-only', 'OPENAI_API_KEY': '', 'UNRELATED': 'keep'}
        before = dict(os.environ)
        result = self.load(original)
        self.assertEqual(result, {**original, 'OPENAI_API_KEY': 'file-only'})
        self.assertEqual(original['OPENAI_API_KEY'], '')
        self.assertIsNot(result, original)
        self.assertEqual(os.environ, before)

    def test_unknown_names_refused_even_when_shell_would_override(self):
        self.path.write_text('EXTRA_' + self.synthetic + '=' + self.synthetic + '\n')
        with self.assertRaises(demo.DemoError) as error:
            self.load()
        self.assertNotIn(self.synthetic, str(error.exception))
        self.assertIn('only RASA_LICENSE', str(error.exception))

    def test_export_and_whitespace_before_equals_are_not_assignment_names(self):
        for prefix in ('export RASA_LICENSE=', 'RASA_LICENSE ='):
            self.path.write_text(prefix + self.synthetic + '\n')
            with self.assertRaises(demo.DemoError) as error:
                self.load()
            self.assertIn('only RASA_LICENSE', str(error.exception))
            self.assertNotIn(self.synthetic, str(error.exception))

    def test_malformed_duplicate_invalid_utf8_and_oversize_never_echo(self):
        for raw in [(self.synthetic + '\n').encode(),
                    ('RASA_LICENSE=' + self.synthetic + '\nRASA_LICENSE=again\n').encode(),
                    ('RASA_LICENSE="' + self.synthetic + '\n').encode(),
                    b'RASA_LICENSE=\xff', b'#' + b'x' * 4096]:
            with self.subTest(kind=raw[:1]):
                self.path.write_bytes(raw)
                with self.assertRaises(demo.DemoError) as error:
                    self.load()
                self.assertNotIn(self.synthetic, str(error.exception))

    def test_tracked_file_refused_before_reading_even_if_worktree_deleted(self):
        self.path.write_text('RASA_LICENSE=' + self.synthetic + '\n')
        demo.subprocess.run(['git', '-C', str(self.root), 'add', '-f', '.env'], check=True,
                            stdout=demo.subprocess.DEVNULL, stderr=demo.subprocess.DEVNULL)
        self.path.unlink()
        with self.assertRaises(demo.DemoError) as error:
            self.load()
        self.assertIn('tracked by Git', str(error.exception))
        self.assertNotIn(self.synthetic, str(error.exception))

    def test_git_redirect_cannot_bypass_tracking_check(self):
        self.path.write_text('RASA_LICENSE=fixture\n')
        demo.subprocess.run(['git', '-C', str(self.root), 'add', '-f', '.env'], check=True,
                            stdout=demo.subprocess.DEVNULL, stderr=demo.subprocess.DEVNULL)
        with self.assertRaises(demo.DemoError):
            self.load({'GIT_INDEX_FILE': str(self.root / 'missing-index')})

    def test_unignored_and_group_world_writable_and_nonregular_refused(self):
        self.path.write_text('RASA_LICENSE=fixture-only\n')
        (self.root / '.gitignore').unlink()
        with self.assertRaises(demo.DemoError):
            self.load()
        (self.root / '.gitignore').write_text('.env\n')
        for mode in (0o620, 0o602):
            self.path.chmod(mode)
            with self.assertRaises(demo.DemoError):
                self.load()
        self.path.unlink()
        self.path.mkdir()
        with self.assertRaises(demo.DemoError):
            self.load()
        self.path.rmdir()
        os.mkfifo(self.path)
        with self.assertRaises(demo.DemoError):
            self.load()

    def test_setup_never_loads_dotenv_or_passes_shell_keys_to_build_processes(self):
        results = [SimpleNamespace(returncode=0, stdout=sys.executable + '\n'), SimpleNamespace(returncode=0)]
        values = {name: 'synthetic-build-secret-' + name for name in demo.PARTICIPANT_KEYS}
        with patch.dict(os.environ, values), \
                patch.object(demo, 'participant_environment', side_effect=AssertionError('setup must not read credentials')), \
                patch.object(demo.subprocess, 'run', side_effect=results) as run, \
                patch.object(demo, 'completed') as completed, \
                patch('demo_make.mark_environment'), \
                patch.object(demo.shutil, 'which', return_value='/installed/uv'):
            demo.setup()
        for call in run.call_args_list:
            self.assertTrue(demo.PARTICIPANT_KEYS.isdisjoint(call.kwargs['env']))
        self.assertEqual(completed.call_count, 2)
        for call in completed.call_args_list:
            self.assertTrue(demo.PARTICIPANT_KEYS.isdisjoint(call.kwargs['env']))
            self.assertEqual(call.kwargs['env']['PYTHON_DOTENV_DISABLED'], '1')
            self.assertEqual(call.kwargs['env']['UV_NO_ENV_FILE'], '1')

    def test_git_failure_is_fixed_refusal(self):
        with patch.object(demo.subprocess, 'run', return_value=SimpleNamespace(returncode=128)):
            with self.assertRaises(demo.DemoError) as error:
                self.load()
        self.assertIn('Git could not verify', str(error.exception))

    def test_only_root_env_exception_nested_env_and_root_variants_refused(self):
        for path in (self.project / '.env', self.worker / '.env', self.root / '.env.local'):
            with self.subTest(location=path.name):
                path.write_text('RASA_LICENSE=' + self.synthetic)
                with self.assertRaises(demo.DemoError) as error:
                    self.load()
                self.assertNotIn(self.synthetic, str(error.exception))
                path.unlink()

    def test_symlink_refused_and_example_is_not_loaded(self):
        (self.root / '.env.example').write_text('NOT_ALLOWED=' + self.synthetic)
        self.assertEqual(self.load(), {})
        self.path.symlink_to(self.root / '.env.example')
        with self.assertRaises(demo.DemoError):
            self.load()

    def test_child_environment_loads_keys_without_global_mutation_and_disables_dotenv(self):
        self.path.write_text('RASA_LICENSE=' + self.synthetic + '\n')
        with patch.object(demo, 'ROOT', self.root), patch.object(demo, 'PROJECT', self.project), \
                patch.object(demo, 'WORKER', self.worker), patch.dict(os.environ, {}, clear=True):
            output = io.StringIO()
            with redirect_stderr(output):
                result = demo.child_environment()
            self.assertEqual(result['RASA_LICENSE'], self.synthetic)
            self.assertNotIn('RASA_LICENSE', os.environ)
            self.assertEqual(result['UV_NO_ENV_FILE'], '1')
            self.assertEqual(result['PYTHON_DOTENV_DISABLED'], '1')
            self.assertNotIn(self.synthetic, output.getvalue())

    def test_real_engine_dotenv_loader_disabled_by_child_flag(self):
        from rasa.cli.project_env import load_project_dotenv
        self.path.write_text('RASA_LICENSE=' + self.synthetic + '\n')
        with patch.dict(os.environ, {'PYTHON_DOTENV_DISABLED': '1'}, clear=True):
            load_project_dotenv(str(self.root))
            self.assertNotIn('RASA_LICENSE', os.environ)

    def test_cli_refusal_has_no_secret_no_traceback_and_no_children(self):
        self.path.write_text('UNKNOWN=' + self.synthetic + '\n')
        output = io.StringIO()
        with patch.object(demo, 'ROOT', self.root), patch.object(demo, 'PROJECT', self.project), \
                patch.object(demo, 'WORKER', self.worker), \
                patch.object(demo.shutil, 'which', return_value='/installed/uv'), \
                patch.object(demo, 'registry_lock'), \
                patch.object(demo.Children, 'start') as start, redirect_stderr(output):
            self.assertEqual(demo.main(['make-target', 'doctor']), 1)
        self.assertNotIn(self.synthetic, output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())
        start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
