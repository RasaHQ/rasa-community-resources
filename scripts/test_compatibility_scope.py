"""A scoped receipt must say what ran, without installing unrelated projects."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import compatibility
import codespaces_scope
import rasa_projects


class CompatibilityCoverageTests(unittest.TestCase):
    def exercise(self, changed):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = [rasa_projects.Project(root / 'examples/a'), rasa_projects.Project(root / 'examples/b')]
            out = root / 'receipt.json'
            argv = ['compatibility', '--affected', 'push', 'before', 'head', '--out', str(out), '--logs', str(root / 'logs')]
            with contextlib.ExitStack() as stack:
                for module in (rasa_projects, compatibility):
                    stack.enter_context(patch.object(module, 'REPO_ROOT', root))
                stack.enter_context(patch.object(compatibility, 'discover_projects', return_value=projects))
                stack.enter_context(patch.object(codespaces_scope, 'changed_slugs', return_value=changed))
                stack.enter_context(patch.object(compatibility, '_load_dotenv'))
                stack.enter_context(patch.object(compatibility, 'fingerprint', return_value='a' * 64))
                stack.enter_context(patch.object(compatibility, 'read_expected_version', return_value='3.22.0.dev3'))
                runner = stack.enter_context(patch.object(compatibility, 'CheckRunner')).return_value
                runner.run.return_value = True
                stack.enter_context(patch('sys.argv', argv))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                compatibility.main()
                commands = [call.args[1] for call in runner.run.call_args_list]
            return json.loads(out.read_text()), commands

    def test_single_resource_receipt_and_commands_exclude_unrelated_installs(self):
        report, commands = self.exercise({'examples/a'})
        self.assertEqual(report['coverage'], 'affected-resources-only')
        self.assertEqual([p['path'] for p in report['projects']], ['examples/a'])
        self.assertEqual(report['starterPack'], [])
        self.assertEqual([c[2] for c in commands if c[1] == 'scripts/check_project.py'], ['examples/a'])

    def test_unrelated_readme_runs_no_installs_and_claims_no_full_coverage(self):
        report, commands = self.exercise(set())
        self.assertEqual(report['coverage'], 'affected-resources-only')
        self.assertEqual(report['projects'], [])
        self.assertFalse(any(c[0] == 'uv' or 'scripts/check_project.py' in c for c in commands))

    def test_partial_receipt_cannot_replace_the_full_catalog_receipt(self):
        with patch('sys.argv', ['compatibility', '--affected', 'push', 'base', 'head']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                compatibility.main()
        self.assertEqual(error.exception.code, 2)

    def test_shared_or_unknown_history_retains_full_coverage(self):
        report, commands = self.exercise(None)
        self.assertEqual(report['coverage'], 'full')
        self.assertEqual(len(report['projects']), 2)
        self.assertEqual(len(report['starterPack']), 2)
        self.assertTrue(any(c[0] == 'uv' for c in commands))
