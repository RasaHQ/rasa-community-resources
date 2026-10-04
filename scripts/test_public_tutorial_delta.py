"""Publication-boundary regressions, without provider calls or Git mutations."""
import contextlib
import io
import json
import sys
import unittest
from unittest.mock import patch
import check_public_tutorial_delta as boundary


class PublicBoundaryTests(unittest.TestCase):
    def test_private_artifacts_and_credentials_are_rejected(self):
        for path in ['tutorials/x/results/run/results.json', 'docs/internal/report.md',
                     'examples/x/.env', 'x/spend-ledger.json', 'x/archive.bundle']:
            self.assertIsNotNone(boundary.path_problem(path), path)

    def test_source_locks_and_credential_templates_are_allowed(self):
        for path in ['tutorials/x/agent.py', 'tutorials/x/.env.example',
                     'tutorials/x/uv.lock', 'x/caller-audio/manifest.json']:
            self.assertIsNone(boundary.path_problem(path), path)

    def test_zero_spend_is_still_a_captured_measurement(self):
        def git(argv):
            if argv[1] == 'diff':
                return b'catalog/case-builds.json\0'
            if argv[-1].startswith('base:'):
                return b'{"builds": []}'
            return json.dumps({'builds': [{'path': 'tutorial', 'spendUsd': 0}]}).encode()
        with patch.object(sys, 'argv', ['check', '--base', 'base']), \
                patch.object(boundary.subprocess, 'check_output', side_effect=git), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                boundary.main()
            self.assertEqual(error.exception.code, 1)

    def test_audio_regeneration_inputs_exclude_billing(self):
        self.assertTrue(boundary.measured_fields({'files': {'a': {'cost_usd': 0}}}))
        self.assertFalse(boundary.measured_fields({'files': {'a': {'sample_rate': 16000, 'sha256': 'fixture'}}}))


if __name__ == '__main__':
    unittest.main()
