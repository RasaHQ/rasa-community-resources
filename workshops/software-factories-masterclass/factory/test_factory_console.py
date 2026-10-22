"""Read-only console controls; no model, keys or production services.
sow: software-factories-masterclass-SOW-02
"""
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from factory_console import snapshot, render, server_for, read_artifact


class ConsoleControls(unittest.TestCase):
    def setUp(self):
        cache = Path(__file__).resolve().parent / '.console-test-cache'
        cache.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'verification').mkdir()
        (self.root / 'review').mkdir()
        (self.root / 'console.json').write_text(json.dumps({'state': 'BUILDER_RUNNING', 'task': {'request': '<script>bad()</script>'}}))

    def test_builder_status_never_creates_factory_accept_and_html_is_escaped(self):
        state = snapshot(self.root)
        self.assertIsNone(state['decision']['decision'])
        self.assertIn('&lt;script&gt;', render(state))
        self.assertNotIn('<script>', render(state))
        self.assertIn('NOT RUN', render(state))

    def test_brand_tokens_fallbacks_scripted_label_and_pause_are_visible(self):
        state = snapshot(self.root)
        state['mode'] = 'SCRIPTED'
        page = render(state, refresh=False)
        self.assertIn('#FAF6F0', page)
        self.assertIn('#181210', page)
        self.assertIn('Newsreader,Georgia,serif', page)
        self.assertIn('SCRIPTED control', page)
        self.assertIn('no model request', page)
        self.assertNotIn('http-equiv="refresh"', page)
        self.assertNotIn('@font-face', page)
        self.assertNotIn('<script', page)

    def test_existing_factory_decision_checks_diff_and_integration_are_read(self):
        decision = {'decision': 'REJECT', 'reasons': ['protected acceptance failed'], 'checks': [
            {'name': 'protected acceptance', 'passed': False, 'summary': 'FAILED', 'output': 'never shown raw log'}]}
        (self.root / 'verification' / 'decision.json').write_text(json.dumps(decision))
        (self.root / 'review' / 'change.patch').write_text('+ example code\n')
        (self.root / 'integration.json').write_text('{"status":"NOT_INTEGRATED"}')
        state = snapshot(self.root)
        self.assertEqual(state['decision']['decision'], 'REJECT')
        self.assertIn('FAIL', render(state))
        self.assertNotIn('never shown raw log', render(state))
        self.assertIn('+ example code', render(state))

    def test_artifact_symlinks_parent_links_special_files_and_limits_refused(self):
        outside = self.root / 'outside'
        outside.write_text('not served')
        link = self.root / 'link'
        link.symlink_to(outside)
        self.assertIsNone(read_artifact(self.root, 'link'))
        parent_link = self.root / 'parent-link'
        parent_link.symlink_to(self.root / 'review')
        self.assertIsNone(read_artifact(parent_link, 'change.patch'))
        os.mkfifo(self.root / 'pipe')
        self.assertIsNone(read_artifact(self.root, 'pipe'))
        (self.root / 'huge').write_bytes(b'x' * (256 * 1024 + 1))
        self.assertIsNone(read_artifact(self.root, 'huge'))

    def test_full_and_eight_character_host_credentials_not_rendered(self):
        synthetic = 'factory-console-fixture-key-123456789'
        (self.root / 'review' / 'change.patch').write_text(synthetic + ' ' + synthetic[5:13])
        with patch.dict(os.environ, {'OPENAI_API_KEY': synthetic}):
            output = render(snapshot(self.root))
        self.assertNotIn(synthetic, output)
        self.assertNotIn(synthetic[5:13], output)

    def test_real_http_has_only_read_endpoints_and_no_path_escape(self):
        server = server_for(self.root, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            for url, expected in [('/', 200), ('/paused', 200), ('/state.json', 200), ('/../outside', 404), ('/.env', 404), ('/?key=fixture', 404)]:
                client.request('GET', url)
                response = client.getresponse()
                self.assertEqual(response.status, expected)
                if expected == 200:
                    self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                response.read()
            client.request('POST', '/', body='execute')
            response = client.getresponse()
            self.assertEqual(response.status, 405)
            response.read()
            client.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_future_run_is_read_only_waiting_and_malformed_records_do_not_claim_pass(self):
        future = self.root / 'future-run'
        server = server_for(future, port=0)
        try:
            self.assertFalse(future.exists())
            self.assertEqual(snapshot(future)['state'], 'WAITING')
        finally:
            server.server_close()
        (self.root / 'verification' / 'decision.json').write_text('{"checks":null}')
        self.assertEqual(snapshot(self.root)['checks'], [])

    def test_bind_and_expiry_are_enforced(self):
        for host in ('0.0.0.0', '8.8.8.8', '::', 'localhost'):
            with self.assertRaises(ValueError):
                server_for(self.root, host=host, port=0)
        with self.assertRaises(ValueError):
            server_for(self.root, host='100.64.0.7', port=0)
        with self.assertRaises(ValueError):
            server_for(self.root, host='100.64.0.7', port=0, expires_at=datetime(2026, 10, 23, tzinfo=timezone.utc))
        expiry = datetime(2026, 10, 22, 16, 30, tzinfo=timezone.utc)
        server = server_for(self.root, port=0, expires_at=expiry, clock=lambda: expiry)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            client.request('GET', '/')
            response = client.getresponse()
            self.assertEqual(response.status, 410)
            response.read()
            client.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
