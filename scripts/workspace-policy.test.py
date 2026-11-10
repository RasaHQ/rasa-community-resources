"""Bulk targets must refuse before creating environments in a worktree."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


class BulkEnvironmentPolicy(unittest.TestCase):
    def test_bulk_install_requires_explicit_scope_before_sync(self):
        makefile = Path(__file__).resolve().parents[1] / 'Makefile'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'fixture').mkdir()
            log = root / 'uv-calls'
            uv = root / 'uv'
            uv.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> ' + shlex.quote(str(log)) + '\n')
            uv.chmod(0o700)
            result = subprocess.run(
                ['make', '-f', str(makefile), 'install-all', 'ALL_PROJECTS=0',
                 f'ROOT={root}', 'PROJECTS=fixture', f'UV={uv}'],
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Full-catalog installs require ALL_PROJECTS=1', result.stdout)
            self.assertFalse(log.exists())
            allowed = subprocess.run(
                ['make', '-f', str(makefile), '_require-all-environments', 'ALL_PROJECTS=1'],
                text=True, capture_output=True,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)


if __name__ == '__main__':
    unittest.main()
