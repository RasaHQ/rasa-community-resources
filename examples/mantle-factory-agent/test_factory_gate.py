"""Real protected-gate integration cases. sow: software-factories-masterclass-SOW-02"""
import hashlib
import unittest

import factory_gate


class FactoryGateTests(unittest.TestCase):
    def protected_hashes(self):
        root = factory_gate._pack()
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob('*') if path.is_file() and '__pycache__' not in path.parts}

    def test_good_attempt_accepts_and_preserves_the_source(self):
        before = self.protected_hashes()
        result = factory_gate.run_factory('good')
        self.assertEqual(result['verdict'], 'ACCEPT', result)
        self.assertIsNone(result['failing_test'])
        self.assertRegex(result['fingerprint'], r'^[0-9a-f]{64}$')
        self.assertGreater(result['seconds'], 0)
        self.assertEqual(self.protected_hashes(), before)

    def test_ignoring_limit_rejects_with_b1_and_preserves_the_source(self):
        before = self.protected_hashes()
        result = factory_gate.run_factory('ignores-limit')
        self.assertEqual(result['verdict'], 'REJECT', result)
        self.assertEqual(result['failing_test'], 'test_b1_four_currencies_show_at_most_the_limit')
        self.assertRegex(result['fingerprint'], r'^[0-9a-f]{64}$')
        self.assertGreater(result['seconds'], 0)
        self.assertEqual(self.protected_hashes(), before)


if __name__ == '__main__':
    unittest.main()
