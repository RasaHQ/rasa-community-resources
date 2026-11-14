import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from admission import decide
from index import held
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

    def test_a_held_version_is_never_a_candidate(self):
        data = releases('3.21.0.dev5', '3.22.0.dev4')
        hold = {'held': '>=3.22.0.dev0', 'reason': 'ignores keys the catalog relies on'}
        result = decide('3.21.0.dev5', data, hold=hold)
        self.assertEqual(result['status'], 'held')
        self.assertEqual(result['reason'], 'ignores keys the catalog relies on')
        self.assertEqual(decide('3.21.0.dev5', releases('3.21.0.dev5', '3.21.1'), hold=hold)['status'], 'candidate')
        self.assertEqual(decide('3.21.0.dev5', data)['status'], 'candidate')
        with self.assertRaisesRegex(ValueError, 'non-empty'):
            held('3.22.0.dev4', {'held': '>=3.22.0.dev0'})

    def test_the_newest_unheld_release_is_still_proposed_during_a_hold(self):
        hold = {'held': '>=3.22.0.dev0', 'reason': 'held for testing'}
        data = releases('3.21.0.dev5', '3.21.1', '3.22.0.dev4')
        result = decide('3.21.0.dev5', data, hold=hold)
        self.assertEqual(result, {'status': 'candidate', 'version': '3.21.1'})
        self.assertEqual(decide('3.21.1', data, hold=hold)['status'], 'held')

    def test_discovery_selects_the_same_unheld_release(self):
        from index import discover
        hold = {'held': '>=3.22.0.dev0', 'reason': 'held for testing'}
        data = releases('3.21.0.dev5', '3.21.1', '3.22.0.dev4')
        seen = []
        report = discover(data, inspect=lambda v: seen.append(v) or {'version': v, 'mantlePresent': True}, hold=hold)
        self.assertEqual(report['selected']['version'], '3.21.1')
        self.assertNotIn('3.22.0.dev4', seen)

    BAD_HOLDS = ('{}', '[]', 'false', 'null', '0', '""', '"  "', '{"held": "", "reason": "x"}',
                 '{"held": ">=3.22.0.dev0", "reason": ""}', '{"held": "not a range", "reason": "x"}', 'not json')

    def test_a_present_but_malformed_hold_fails_closed_in_admission(self):
        import admission, index
        data = releases('3.21.0.dev5', '3.22.0.dev4')
        for content in self.BAD_HOLDS:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'RASA_RELEASE_HOLD.json'
                path.write_text(content)
                with patch.object(index, 'HOLD', path), patch('admission.get_json', return_value=data), \
                        patch('maintenance.execute') as execute, patch('maintenance.handoff'), \
                        patch('maintenance.subprocess.check_output', return_value='a' * 40):
                    with self.assertRaises(ValueError):
                        admission.check()
                    self.assertEqual(run('catalog', 'companion', Path(tmp) / 'out'), 1)
                    execute.assert_not_called()

    def test_a_present_but_malformed_hold_fails_closed_in_discovery(self):
        import index
        data = releases('3.21.0.dev5', '3.22.0.dev4')
        for content in self.BAD_HOLDS:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'RASA_RELEASE_HOLD.json'
                path.write_text(content)
                inspected = []
                with patch.object(index, 'HOLD', path), self.assertRaises(ValueError):
                    index.discover(data, inspect=lambda v: inspected.append(v) or {'version': v, 'mantlePresent': True})
                self.assertEqual(inspected, [])

    def test_only_an_absent_hold_file_lifts_the_hold(self):
        import index
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(index.load_hold(Path(tmp) / 'RASA_RELEASE_HOLD.json'))

    def test_the_repository_hold_covers_every_3_22_prerelease(self):
        import json
        hold = json.loads((Path(__file__).resolve().parents[2] / 'RASA_RELEASE_HOLD.json').read_text())
        for version in ('3.22.0.dev4', '3.22.0.dev9', '3.22.0rc1', '3.22.0'):
            self.assertIsNotNone(held(version, hold), version)
        self.assertIsNone(held('3.21.0.dev5', hold))

    def test_noop_never_downloads_migrates_or_checks_credentials(self):
        for status in ('unchanged', 'open-candidate', 'held'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                with patch('admission.check', return_value={'status': status, 'version': '3.22.0.dev3'}), patch('maintenance.execute') as execute, patch('maintenance.handoff'), patch('maintenance.subprocess.check_output', return_value='a' * 40), patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(run('catalog', 'companion', Path(tmp)), 0)
                    execute.assert_not_called()

    def test_admission_errors_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('admission.check', side_effect=OSError('index unavailable')), patch('maintenance.execute') as execute, patch('maintenance.handoff'), patch('maintenance.subprocess.check_output', return_value='a' * 40):
                self.assertEqual(run('catalog', 'companion', Path(tmp)), 1)
                execute.assert_not_called()
