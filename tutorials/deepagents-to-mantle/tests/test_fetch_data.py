"""Wrong existing data is preserved without a network request."""
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch


class PinnedData(unittest.TestCase):
    def test_wrong_existing_file_is_preserved_without_network(self):
        source = Path(__file__).resolve().parents[1] / 'fetch_data.py'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / 'fetch_data.py'
            script.write_bytes(source.read_bytes())
            (root / 'data').mkdir()
            data = root / 'data/chinook.sqlite'
            original = b'unverified data that must not be overwritten'
            data.write_bytes(original)
            with patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected network')):
                with self.assertRaisesRegex(SystemExit, 'checksum mismatch'):
                    runpy.run_path(str(script), run_name='__main__')
            self.assertEqual(data.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
