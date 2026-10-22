"""Protected data-only recovery configuration requirements; no candidate code is imported.
sow: software-factories-masterclass-SOW-02
"""
import json
import os
from pathlib import Path
import unittest

TASK = json.loads((Path(__file__).resolve().parent.parent / 'tasks/c-recovery-attempts.json').read_text())
PATH = Path(os.environ['PRODUCT_PROJECT']) / 'recovery.json'


def read_policy():
    try:
        if PATH.stat().st_size > 16384:
            return None
        return json.loads(PATH.read_text())
    except (OSError, ValueError, RecursionError):
        return None


class RecoveryRequirements(unittest.TestCase):
    def test_c1_only_the_two_configuration_fields_exist(self):
        policy = read_policy()
        self.assertIsInstance(policy, dict)
        self.assertEqual(set(policy), {'max_attempts', 'retry_rejected'})

    def test_c2_attempt_count_is_a_small_whole_number(self):
        policy = read_policy()
        self.assertIsInstance(policy, dict)
        self.assertIs(type(policy.get('max_attempts')), int)
        self.assertIn(policy['max_attempts'], (1, 2, 3))

    def test_c3_attempt_count_matches_the_public_request(self):
        policy = read_policy()
        self.assertIsInstance(policy, dict)
        self.assertEqual(policy.get('max_attempts'), TASK['target_attempts'])

    def test_c4_a_rejected_change_is_never_retried(self):
        policy = read_policy()
        self.assertIsInstance(policy, dict)
        self.assertIs(policy.get('retry_rejected'), False)


if __name__ == '__main__':
    unittest.main()
