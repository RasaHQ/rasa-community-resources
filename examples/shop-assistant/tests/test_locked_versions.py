"""Release changes retain exact installed-package enforcement."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from shop_demo.locked_versions import require_locked_version


class LockedVersionTests(unittest.TestCase):
    def check(self, lock, installed, distribution='mcp'):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'uv.lock').write_text(lock)
            with patch('shop_demo.locked_versions.version', return_value=installed):
                require_locked_version(directory, distribution)

    def test_current_and_stable_locks_select_their_own_exact_versions(self):
        for name, resolved in [('mcp', '1.28.1'), ('mcp', '1.30.0'),
                               ('rasa-pro', '3.21.0.dev5'), ('rasa-pro', '3.21.4')]:
            self.check(f'[[package]]\nname="{name}"\nversion="{resolved}"\n', resolved, name)

    def test_another_installed_version_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'must match uv.lock'):
            self.check('[[package]]\nname="mcp"\nversion="1.30.0"\n', '1.28.1')

    def test_missing_ambiguous_and_invalid_locks_refuse(self):
        for lock in ['', 'not toml', '[[package]]\nname="mcp"\nversion="1.28.1"\n[[package]]\nname="mcp"\nversion="1.30.0"\n']:
            with self.assertRaises(RuntimeError):
                self.check(lock, '1.28.1')


if __name__ == '__main__':
    unittest.main()
