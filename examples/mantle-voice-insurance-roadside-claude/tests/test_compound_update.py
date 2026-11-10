"""Rejected compound edits preserve both draft data and its confirmation version."""
import dataclasses
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
from lib import roadside as hc


class CompoundUpdateTests(unittest.TestCase):
    def setUp(self):
        self.service = hc.RoadsideService('compound-edit')
        result, self.draft = hc.start_dispatch_draft(
            self.service, 'HC-AU-517306', 'VEH-5173-1', 'tow', 'exit 14')
        self.assertIsNotNone(self.draft, result)
        self.before = dataclasses.asdict(self.draft)
        self.memory = hc.memory_values(self.service, self.draft)

    def assert_rejected_without_change(self, expected, **changes):
        result, draft = hc.update_dispatch_draft(self.service, self.draft.draft_id, **changes)
        self.assertEqual(result['status'], expected)
        self.assertIsNone(draft)
        self.assertEqual(dataclasses.asdict(self.service.drafts[self.draft.draft_id]), self.before)
        self.assertEqual(hc.memory_values(self.service, self.draft), self.memory)
        self.assertEqual(self.service.dispatches, [])

    def test_bad_service_does_not_save_earlier_location_edit(self):
        self.assert_rejected_without_change('unsupported_service', location='exit 16',
                                            service_needed='not-a-service')

    def test_bad_vehicle_does_not_save_earlier_location_edit(self):
        self.assert_rejected_without_change('unknown_vehicle', location='exit 16',
                                            vehicle_ref='not-a-vehicle')

    def test_bad_vehicle_does_not_save_earlier_service_edit(self):
        self.assert_rejected_without_change('unknown_vehicle', service_needed='jump_start',
                                            vehicle_ref='not-a-vehicle')

    def test_valid_compound_edit_keeps_object_and_advances_version_once(self):
        result, draft = hc.update_dispatch_draft(self.service, self.draft.draft_id,
                                                 location='exit 16', service_needed='jump_start')
        self.assertIs(draft, self.draft)
        self.assertEqual((result['status'], draft.place_ref, draft.service, draft.version),
                         ('updated', 'R12-N-EXIT16', 'jump_start', self.before['version'] + 1))
        self.assertNotEqual(hc.memory_values(self.service, draft)['pending_draft_ref'],
                            self.memory['pending_draft_ref'])
        self.assertEqual(self.service.dispatches, [])


if __name__ == '__main__':
    unittest.main()
