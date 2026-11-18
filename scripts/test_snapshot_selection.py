"""Exercise the production snapshot workflow without installing any resource."""
from pathlib import Path
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


def snapshot_run_block():
    """Read the actual YAML run block using its name and indentation."""
    workflow = (REPO / '.github/workflows/validate.yml').read_text()
    section = workflow.split('      - name: check frozen snapshots\n', 1)[1]
    lines = section.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == 'run: |')
    width = len(lines[start]) - len(lines[start].lstrip()) + 2
    body = []
    for line in lines[start + 1:]:
        if line.strip() and not line.startswith(' ' * width):
            break
        body.append(line[width:] if line.strip() else '')
    return '\n'.join(body) + '\n'


class SnapshotSelectionTests(unittest.TestCase):
    def run_workflow(self, payload, *, selector_exit=0, checker_exit=0):
        with tempfile.TemporaryDirectory(prefix='snapshot workflow ') as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / 'bin').mkdir()
            # Fake only the resource checker. No packages, model or provider is used.
            (root / 'scripts/check_project.py').write_text(
                'import json, os, sys\n'
                'from pathlib import Path\n'
                'with Path(os.environ["SNAPSHOT_TEST_CALLS"]).open("a") as output:\n'
                '    output.write(json.dumps(sys.argv[1:]) + "\\n")\n'
                'raise SystemExit(int(os.environ["SNAPSHOT_TEST_CHECKER_EXIT"]))\n')
            # Force the selector producer itself to fail, keeping the real shell block.
            python = root / 'bin/python'
            python.write_text('#!/bin/sh\n'
                'if [ "$1" = "-c" ] && [ "$SNAPSHOT_TEST_SELECTOR_EXIT" != "0" ]; then\n'
                '  exit "$SNAPSHOT_TEST_SELECTOR_EXIT"\n'
                'fi\n'
                'exec ' + shlex.quote(sys.executable) + ' "$@"\n')
            python.chmod(0o755)
            calls = root / 'calls.jsonl'
            env = {**os.environ,
                'PATH': str(root / 'bin') + os.pathsep + os.environ.get('PATH', ''),
                'SNAPSHOTS': payload,
                'RUNNER_TEMP': str(root),
                'GITHUB_STEP_SUMMARY': str(root / 'summary.md'),
                'SNAPSHOT_TEST_CALLS': str(calls),
                'SNAPSHOT_TEST_SELECTOR_EXIT': str(selector_exit),
                'SNAPSHOT_TEST_CHECKER_EXIT': str(checker_exit)}
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', snapshot_run_block()],
                cwd=root, env=env, capture_output=True, text=True, timeout=10)
            invoked = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
            leftovers = [path.name for path in root.glob('snapshot-projects.*')]
            return result, invoked, leftovers

    def test_valid_empty_selection_is_an_explicit_skip(self):
        result, invoked, leftovers = self.run_workflow('[]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('No frozen wave projects to check.', result.stdout)
        self.assertEqual(invoked, [])
        self.assertEqual(leftovers, [])

    def test_valid_selection_checks_each_project(self):
        result, invoked, leftovers = self.run_workflow('["snapshots/red", "snapshots/blue"]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(invoked, [['snapshots/red', '--use-project-pin'],
                                   ['snapshots/blue', '--use-project-pin']])
        self.assertEqual(leftovers, [])

    def test_invalid_json_fails_before_empty_success_or_resource_checks(self):
        result, invoked, leftovers = self.run_workflow('not valid JSON')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('No frozen wave projects to check.', result.stdout)
        self.assertEqual(invoked, [])
        self.assertEqual(leftovers, [])

    def test_failed_selector_preserves_its_exit_and_does_not_pass_empty(self):
        result, invoked, leftovers = self.run_workflow('[]', selector_exit=17)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertNotIn('No frozen wave projects to check.', result.stdout)
        self.assertEqual(invoked, [])
        self.assertEqual(leftovers, [])

    def test_resource_failure_still_fails_the_workflow(self):
        result, invoked, leftovers = self.run_workflow('["snapshots/red"]', checker_exit=19)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(invoked, [['snapshots/red', '--use-project-pin']])
        self.assertIn('failed its own-pin check', result.stdout)
        self.assertEqual(leftovers, [])


if __name__ == '__main__':
    unittest.main()
