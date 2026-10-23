"""Unknown dependency pins must not silently reuse the private voice repair."""
import unittest
from importlib.metadata import PackageNotFoundError
from voice_compat import require_qualified_voice_pins
class VoiceCompatibilityTests(unittest.TestCase):
    def test_known_backend_pairs(self):
        for core in ['0.35.6','0.36.3']:
            self.assertEqual(require_qualified_voice_pins({'rasa-pro':'3.21.0.dev5','zeocore':core}.__getitem__),('3.21.0.dev5',core))
    def test_either_pin_change_needs_requalification(self):
        for rasa,core in [('3.21.0.dev12','0.36.3'),('3.21.0','0.36.3'),('3.21.0.dev5','0.36.4')]:
            with self.assertRaisesRegex(RuntimeError,'requalification'):
                require_qualified_voice_pins({'rasa-pro':rasa,'zeocore':core}.__getitem__)
    def test_missing_dependency_has_fixed_message(self):
        def absent(_):raise PackageNotFoundError('not installed')
        with self.assertRaisesRegex(RuntimeError,'dependencies are missing'):require_qualified_voice_pins(absent)
