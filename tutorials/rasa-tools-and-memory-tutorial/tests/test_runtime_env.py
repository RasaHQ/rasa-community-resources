"""Credential routing controls use placeholders only; never a real key."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_rasa.py'


@unittest.skipUnless(importlib.util.find_spec('dotenv'), 'Use the locked tutorial interpreter')
class SelectedCredentialFile(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('tutorial_runner', SCRIPT)
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / '.env'

    def test_local_values_override_inherited_credentials(self):
        self.path.write_text('RASA_LICENSE=LOCAL_LICENSE_PLACEHOLDER\nOPENAI_API_KEY=LOCAL_KEY_PLACEHOLDER\n')
        result = self.runner.environment(self.path, {'PATH': '/example', 'OPENAI_API_KEY': 'OTHER_PROJECT_PLACEHOLDER', 'RASA_PRO_LICENSE': 'OTHER_LICENSE_PLACEHOLDER', 'OTHER_API_KEY': 'UNRELATED_PLACEHOLDER'})
        self.assertEqual(result['OPENAI_API_KEY'], 'LOCAL_KEY_PLACEHOLDER')
        self.assertEqual(result['RASA_LICENSE'], 'LOCAL_LICENSE_PLACEHOLDER')
        self.assertNotIn('OTHER_API_KEY', result)
        self.assertEqual(result['PATH'], '/example')

    def test_other_dotenv_and_inherited_passwords_are_excluded(self):
        import os
        from unittest.mock import patch
        from dotenv import load_dotenv
        self.path.write_text('RASA_LICENSE=LOCAL_LICENSE_PLACEHOLDER\n')
        other = Path(self.temp.name) / 'other.env'
        other.write_text('OTHER_API_KEY=OTHER_FILE_PLACEHOLDER\n')
        result = self.runner.environment(self.path, {'DB_PASSWORD': 'OTHER_PASSWORD_PLACEHOLDER', 'CLOUD_CREDENTIALS': 'OTHER_CREDENTIAL_PLACEHOLDER'})
        self.assertNotIn('DB_PASSWORD', result)
        self.assertNotIn('CLOUD_CREDENTIALS', result)
        self.assertNotIn('RASA_PRO_LICENSE', result)
        with patch.dict(os.environ, result, clear=True):
            load_dotenv(other, override=False)
            self.assertNotIn('OTHER_API_KEY', os.environ)

    def test_empty_local_key_does_not_use_shell_key(self):
        self.path.write_text('RASA_LICENSE=LOCAL_LICENSE_PLACEHOLDER\nOPENAI_API_KEY=\n')
        result = self.runner.environment(self.path, {'OPENAI_API_KEY': 'OTHER_PROJECT_PLACEHOLDER'})
        self.assertEqual(result['OPENAI_API_KEY'], '')

    def test_missing_local_license_does_not_use_shell_license(self):
        self.path.write_text('OPENAI_API_KEY=LOCAL_KEY_PLACEHOLDER\n')
        with self.assertRaises(ValueError):
            self.runner.environment(self.path, {'RASA_PRO_LICENSE': 'OTHER_LICENSE_PLACEHOLDER'})

    def test_missing_file_is_refused(self):
        with self.assertRaises(ValueError):
            self.runner.environment(self.path, {})


if __name__ == '__main__':
    unittest.main()
