"""Projection, request-boundary and total-deadline controls; no SDK or provider."""
import http.server
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('tracker', Path(__file__).resolve().parents[1] / 'voice_tracker.py')
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


class TrackerControls(unittest.TestCase):
    def test_only_numeric_server_metrics_survive_and_missing_is_not_zero(self):
        result = v.project({'sender_id': 'PRIVATE', 'events': [
            {'event': 'user', 'text': 'PRIVATE'},
            {'event': 'bot_turn_ended', 'metadata': {'secret': 'PRIVATE', 'latency_breakdown': {
                'user_perceived_latency_ms': 100, 'first_voice_response': {'tts_time_to_first_byte_ms': 0},
                'first_agent_response': {'llm_total_generation_ms': True}}}}]})
        self.assertNotIn('PRIVATE', json.dumps(result))
        metrics = result['turns'][0]['metrics']
        self.assertEqual(metrics['server_trigger_to_first_output_ms'], 100)
        self.assertEqual(metrics['tts_first_byte_ms'], 0)
        self.assertIsNone(metrics['tts_generation_ms'])
        self.assertEqual(result['turns'][0]['invalid_metrics'], ['llm_generation_ms'])
        self.assertEqual(result['browser_clock_join'], 'not_established')

    def test_empty_projection_is_not_a_completed_phase_collection(self):
        for tracker in ({'events': []}, {'events': [{'event': 'bot_turn_ended'}]}):
            self.assertEqual(v.project(tracker)['status'], 'no_phase_values')

    def test_dot_segments_and_zero_port_never_connect(self):
        with patch.object(v.http.client, 'HTTPConnection') as connect:
            for url, identity in (('http://127.0.0.1', '.'), ('http://127.0.0.1', '..'), ('http://127.0.0.1:0', 'fixture')):
                with self.assertRaises(ValueError):
                    v.fetch(url, identity, 1)
            connect.assert_not_called()

    def test_existing_artifact_never_triggers_a_second_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'snapshot.json'
            output.write_text('original')
            with patch.object(v, 'fetch') as fetch:
                with self.assertRaises(FileExistsError):
                    v.collect('http://127.0.0.1:5005', 'fixture-session', output)
                fetch.assert_not_called()
            self.assertEqual(output.read_text(), 'original')

    def test_failure_receipt_retains_no_url_identity_or_error_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'snapshot.json'
            with patch.object(v, 'fetch', side_effect=ValueError('PRIVATE')):
                self.assertEqual(v.collect('PRIVATE', 'PRIVATE', output), 1)
            text = output.read_text()
            self.assertNotIn('PRIVATE', text)
            self.assertEqual(json.loads(text)['status'], 'not_collected')
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_nonlocal_or_credentialed_api_is_refused_before_connect(self):
        with patch.object(v.http.client, 'HTTPConnection') as connect:
            for url in ('https://127.0.0.1', 'http://example.com', 'http://token@127.0.0.1', 'http://127.0.0.1/?token=PRIVATE'):
                with self.assertRaises(ValueError):
                    v.fetch(url, 'fixture-session', .1)
            connect.assert_not_called()

    def test_local_success_projects_metadata_and_redirect_is_not_followed(self):
        paths = []
        body = json.dumps({'sender_id': 'PRIVATE', 'events': [
            {'event': 'bot_turn_ended', 'metadata': {'latency_breakdown': {
                'first_voice_response': {'tts_time_to_first_byte_ms': 123.5}}}}]}).encode()
        class Local(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                paths.append(self.path)
                if 'redirect-session' in self.path:
                    self.send_response(302)
                    self.send_header('Location', 'http://external.invalid/PRIVATE')
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Local)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            report = v.fetch(url, 'fixture-session', 1)
            self.assertEqual(report['turns'][0]['metrics']['tts_first_byte_ms'], 123.5)
            self.assertNotIn('PRIVATE', json.dumps(report))
            with self.assertRaises(ValueError):
                v.fetch(url, 'redirect-session', 1)
            self.assertEqual(paths, ['/conversations/fixture-session/tracker',
                                     '/conversations/redirect-session/tracker'])
        finally:
            server.shutdown()
            server.server_close()

    def test_slow_drip_body_cannot_extend_total_request_deadline(self):
        class Slow(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', '10000')
                self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(b' ')
                        self.wfile.flush()
                        time.sleep(.02)
                except OSError:
                    pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Slow)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started = time.monotonic()
        try:
            with self.assertRaises((TimeoutError, OSError, v.http.client.IncompleteRead)):
                v.fetch(f'http://127.0.0.1:{server.server_port}', 'fixture-session', .15)
            self.assertLess(time.monotonic() - started, 1.5)
        finally:
            server.shutdown()
            server.server_close()
