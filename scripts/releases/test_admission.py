import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from admission import decide
from maintenance import run


def releases(*versions):
    return {'releases': {v: [{'filename': 'rasa.whl', 'yanked': False}] for v in versions}}


class AdmissionTests(unittest.TestCase):
    def test_unchanged_and_existing_same_repository_candidate_are_noops(self):
        data = releases('3.21.0.dev5', '3.22.0.dev3')
        self.assertEqual(decide('3.22.0.dev3', data)['status'], 'unchanged')
        pr = {'headRefName': 'automation/rasa-3.22.0.dev3', 'baseRefName': 'main',
              'headRepositoryOwner': {'login': 'RasaHQ'}, 'url': 'https://github.com/RasaHQ/repo/pull/1'}
        self.assertEqual(decide('3.21.0.dev5', data, [pr], 'RasaHQ')['status'], 'open-candidate')
        pr['headRepositoryOwner']['login'] = 'foreign-fork'
        self.assertEqual(decide('3.21.0.dev5', data, [pr], 'RasaHQ')['status'], 'candidate')
        with self.assertRaisesRegex(ValueError, 'downgrade'):
            decide('4.0.0', data)
        with self.assertRaisesRegex(ValueError, 'No usable'):
            decide('3.21.0', releases())

    def test_noop_never_downloads_migrates_or_checks_credentials(self):
        for status in ('unchanged', 'open-candidate'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                with patch('admission.check', return_value={'status': status, 'version': '3.22.0.dev3'}), patch('maintenance.execute') as execute, patch('maintenance.handoff'), patch('maintenance.subprocess.check_output', return_value='a' * 40), patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(run('catalog', 'companion', Path(tmp)), 0)
                    execute.assert_not_called()

    def test_admission_errors_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('admission.check', side_effect=OSError('index unavailable')), patch('maintenance.execute') as execute, patch('maintenance.handoff'), patch('maintenance.subprocess.check_output', return_value='a' * 40):
                self.assertEqual(run('catalog', 'companion', Path(tmp)), 1)
                execute.assert_not_called()
