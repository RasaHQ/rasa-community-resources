import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from maintenance import execute, handoff, redact, run
from propose import allowed_path, changed_identity


class MaintenanceTests(unittest.TestCase):
    def test_failed_command_and_timeout_produce_reproducible_redacted_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch.dict(os.environ, {'RASA_LICENSE': 'private-license-value'}):
                result = execute('training', [sys.executable, '-c', "print('private-license-value'); raise SystemExit(7)"], out)
            self.assertEqual(result['exitCode'], 7)
            self.assertNotIn('private-license-value', (out / result['log']).read_text())
            self.assertEqual(execute('timeout', [sys.executable, '-c', 'import time; time.sleep(3)'], out, .02)['exitCode'], 124)

    def test_redaction_scrubs_tokens_and_authenticated_urls(self):
        result = redact('abc-token https://name:password@example.org/repo', {'GH_TOKEN': 'abc-token'})
        self.assertNotIn('abc-token', result)
        self.assertNotIn('password', result)

    def test_new_companion_commit_at_same_version_is_an_update(self):
        old = {'selected': {'version': '3.20.0rc1'}, 'companionRevision': 'a' * 40}
        self.assertFalse(changed_identity(old, dict(old)))
        self.assertTrue(changed_identity({**old, 'companionRevision': 'b' * 40}, old))

    def test_automation_does_not_stage_workflows_secrets_or_authored_site_articles(self):
        for path in ('.env', '.github/workflows/rasa-release.yml', 'scripts/releases/propose.py', 'src/content/guides/first-agent.md'):
            self.assertFalse(allowed_path(path, True))
            self.assertFalse(allowed_path(path, False))
        self.assertTrue(allowed_path('examples/quickstart/uv.lock', True))
        self.assertTrue(allowed_path('tutorials/example/README.md', False))
        self.assertTrue(allowed_path('docs/MIGRATING.md', False))
        self.assertTrue(allowed_path('community/samrudh-gemini-voice-agent/pyproject.toml', False))
        self.assertTrue(allowed_path('community/samrudh-gemini-voice-agent/uv.lock', False))
        self.assertFalse(allowed_path('docs/arbitrary.md', False))
        self.assertFalse(allowed_path('heroes/example/pyproject.toml', False))

    def test_packet_survives_setup_failure_and_explains_dependency_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            # Isolate this fixture from real working-tree files and SDK logs.
            with patch('maintenance.subprocess.run', return_value=subprocess.CompletedProcess([], 0, stdout='')), patch('maintenance.Path.exists', return_value=False):
                state = handoff(out, 'site', 'failure')
            self.assertEqual(state['status'], 'setup-failed')
            (out / 'discovery.log').write_text('Companion catalog has not adopted the candidate yet.')
            (out / 'run.json').write_text(json.dumps({'status': 'failed', 'steps': [{'step': 'discovery', 'command': ['python', 'scripts/releases/update.py'], 'exitCode': 1, 'log': 'discovery.log'}]}))
            with patch('maintenance.subprocess.run', return_value=subprocess.CompletedProcess([], 0, stdout='')):
                state = handoff(out, 'site')
            self.assertEqual(state['category'], 'companion-update')
            self.assertIn('scripts/releases/update.py', (out / 'HANDOFF.md').read_text())

    def test_failed_gate_never_reaches_proposal_or_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            seen = []
            def fail(label, command, output, timeout):
                seen.append(label)
                (output / (label + '.log')).write_text('broken release')
                return {'step': label, 'command': command, 'exitCode': 1, 'log': label + '.log'}
            with patch('maintenance.execute', side_effect=fail), patch('maintenance.handoff'), patch('maintenance.subprocess.check_output', return_value='a' * 40), patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}):
                self.assertEqual(run('site', 'companion', Path(directory), True), 1)
            self.assertEqual(seen, ['release-tests'])


if __name__ == '__main__':
    unittest.main()
