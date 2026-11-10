import unittest
from pathlib import Path
from unittest.mock import patch
from inventory import source_file_for
ROOT = Path(__file__).resolve().parents[1]

class SourceLocationControls(unittest.TestCase):
    def test_project_source_is_relative(self):
        source, relative = source_file_for(source_file_for, ROOT)
        self.assertEqual(relative.as_posix(), 'inventory.py')
        self.assertEqual(source, ROOT / 'inventory.py')

    def test_external_source_refusal_does_not_disclose_path(self):
        with patch('inventory.inspect.getsourcefile', return_value=str(ROOT.parent / 'outside.py')):
            with self.assertRaises(ValueError) as error:
                source_file_for(source_file_for, ROOT)
        self.assertEqual(str(error.exception), 'A loaded tool is defined outside the project')
        self.assertNotIn(str(ROOT.parent), str(error.exception))

    def test_missing_source_is_named(self):
        with patch('inventory.inspect.getsourcefile', return_value=None):
            with self.assertRaisesRegex(ValueError, 'no inspectable Python source'):
                source_file_for(source_file_for, ROOT)

    def test_builtin_inspection_failure_is_named(self):
        with self.assertRaisesRegex(ValueError, 'no inspectable Python source'):
            source_file_for(len, ROOT)
