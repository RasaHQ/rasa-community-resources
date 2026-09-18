import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import propose


class ProposalTests(unittest.TestCase):
    def exercise(self, merge_fails=False, paths='RASA_RELEASE.json\0RASA_PRO_VERSION\0', identity_change=True, base_changed=False):
        previous = {'selected': {'version': '3.20.0.dev9'}, 'companionRevision': 'a' * 40}
        current = {'selected': {'version': '3.20.0rc1'}, 'companionRevision': 'b' * 40} if identity_change else previous
        calls = []
        def output(command, **kwargs):
            calls.append(command)
            if command[:3] == ['git', 'show', 'HEAD:RASA_RELEASE.json']:
                return json.dumps(previous)
            if command[:3] == ['git', 'diff', '--name-only']:
                return paths.encode()
            if command[:3] == ['git', 'diff', '--binary']:
                return b'tested diff'
            if command[:2] == ['git', 'rev-parse']:
                return 'c' * 40
            if command[:2] == ['git', 'ls-remote']:
                if command[-1] == 'refs/heads/main':
                    return ('e' if base_changed else 'c') * 40 + '\trefs/heads/main'
                return ''
            if command[:3] == ['gh', 'pr', 'list']:
                return '[]'
            if command[:3] == ['gh', 'pr', 'create']:
                return 'https://github.com/Example/site/pull/1'
            if command[:3] == ['gh', 'pr', 'view']:
                return json.dumps({'state': 'MERGED', 'mergeCommit': {'oid': 'd' * 40}})
            raise AssertionError(command)
        def run(command, **kwargs):
            calls.append(command)
            if merge_fails and command[:3] == ['gh', 'pr', 'merge']:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'RASA_RELEASE.json').write_text(json.dumps(current))
            before = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/main', 'GITHUB_REPOSITORY': 'Example/site', 'GITHUB_RUN_ID': '123'}), patch('sys.argv', ['propose.py', '--state', str(root / 'proposal.json'), '--merge']), patch.object(propose.subprocess, 'check_output', side_effect=output), patch.object(propose.subprocess, 'run', side_effect=run):
                    if base_changed:
                        with self.assertRaisesRegex(SystemExit, 'Main changed'):
                            propose.main()
                    elif merge_fails:
                        with self.assertRaises(subprocess.CalledProcessError):
                            propose.main()
                    elif 'src/' in paths:
                        with self.assertRaisesRegex(SystemExit, 'Unexpected candidate'):
                            propose.main()
                    else:
                        propose.main()
                return calls, json.loads((root / 'proposal.json').read_text())
            finally:
                os.chdir(before)

    def test_exact_tested_commit_is_merged_and_checks_are_dispatched(self):
        calls, state = self.exercise()
        merge = next(c for c in calls if c[:3] == ['gh', 'pr', 'merge'])
        self.assertEqual(merge[-2:], ['--match-head-commit', 'c' * 40])
        self.assertNotIn('--admin', merge)
        self.assertTrue(any(c[:3] == ['gh', 'workflow', 'run'] for c in calls))
        self.assertTrue(state['postMergeChecksDispatched'])
        self.assertEqual(state['status'], 'merged')

    def test_blocked_merge_retains_tested_pr_without_dispatch(self):
        calls, state = self.exercise(merge_fails=True)
        self.assertEqual(state['status'], 'proposed')
        self.assertTrue(state['pr'].endswith('/1'))
        self.assertFalse(any(c[:3] == ['gh', 'workflow', 'run'] for c in calls))

    def test_unchanged_pin_does_not_create_daily_receipt_pr(self):
        calls, state = self.exercise(identity_change=False)
        self.assertEqual(state['status'], 'unchanged')
        self.assertFalse(any(c[0] == 'gh' for c in calls))

    def test_authored_prose_cannot_enter_an_automatic_merge(self):
        calls, _ = self.exercise(paths='src/content/guides/first-agent.md\0')
        self.assertFalse(any(c[:2] == ['git', 'commit'] for c in calls))

    def test_advanced_main_requires_fresh_validation(self):
        calls, state = self.exercise(base_changed=True)
        self.assertFalse(any(c[:2] == ['git', 'push'] for c in calls))
        self.assertFalse(any(c[0] == 'gh' for c in calls))

    def test_non_main_context_cannot_publish(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/feature'}), patch('sys.argv', ['propose.py']):
            with self.assertRaisesRegex(SystemExit, 'trusted main'):
                propose.main()


if __name__ == '__main__':
    unittest.main()
