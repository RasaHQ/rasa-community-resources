"""Exercise setup readiness and secret-safe diagnostics without real SDK calls."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / '.devcontainer/software-factories-workshop'


class WorkshopSetupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = self.root / 'mantle'
        (self.env / 'bin').mkdir(parents=True)
        self.rasa = self.env / 'bin/rasa'
        self.rasa.write_text('#!/bin/bash\nprintf "%s\\n" "$WORKSHOP_TEST_VERSION_OUTPUT"\nexit "$WORKSHOP_TEST_EXIT"\n')
        self.rasa.chmod(0o700)
        uv = self.bin / 'uv'
        uv.write_text('#!/bin/bash\nexit 0\n')
        uv.chmod(0o700)

    def run_setup(self, **changes):
        environment = {
            'PATH': str(self.bin) + ':/usr/bin:/bin',
            'HOME': os.environ['HOME'],
            'WORKSHOP_MANTLE_ENV': str(self.env),
            'RASA_LICENSE': 'fixture-license-sentinel',
            'OPENAI_API_KEY': 'fixture-model-sentinel',
            'WORKSHOP_TEST_VERSION_OUTPUT': 'Rasa Version: 3.21.0.dev5',
            'WORKSHOP_TEST_EXIT': '0',
        }
        environment.update(changes)
        result = subprocess.run(['/bin/bash', str(PROFILE / 'setup.sh')],
                                env=environment, capture_output=True, text=True)
        self.assertNotIn('fixture-license-sentinel', result.stdout + result.stderr)
        self.assertNotIn('fixture-model-sentinel', result.stdout + result.stderr)
        return result

    def test_missing_license_does_not_claim_readiness(self):
        result = self.run_setup(RASA_LICENSE='')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Setup finished', result.stdout)
        self.assertIn('RASA_LICENSE', result.stdout)

    def test_missing_model_key_does_not_claim_readiness(self):
        result = self.run_setup(OPENAI_API_KEY='')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Setup finished', result.stdout)
        self.assertIn('OPENAI_API_KEY', result.stdout)

    def test_rejected_license_output_is_not_echoed(self):
        result = self.run_setup(WORKSHOP_TEST_VERSION_OUTPUT='LicenseEncodingException: fixture-license-sentinel')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Setup finished', result.stdout)

    def test_failed_command_output_is_not_echoed(self):
        result = self.run_setup(WORKSHOP_TEST_EXIT='1', WORKSHOP_TEST_VERSION_OUTPUT='fixture-model-sentinel')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Setup finished', result.stdout)

    def test_prepared_environment_reports_presence_not_provider_success(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 0)
        self.assertIn('Setup finished', result.stdout)
        self.assertIn('presence', result.stdout.replace('is present', 'presence'))

    def test_missing_installation_is_not_a_pass(self):
        self.rasa.unlink()
        self.assertNotEqual(self.run_setup().returncode, 0)

    def test_missing_uv_identifies_wrong_image(self):
        (self.bin / 'uv').unlink()
        result = self.run_setup(PATH=str(self.bin))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('uv is missing', result.stdout)

    def test_profile_uses_the_image_and_no_studio_service(self):
        lines = (PROFILE / 'devcontainer.json').read_text().splitlines()
        config = json.loads('\n'.join(line for line in lines if not line.lstrip().startswith('//')))
        self.assertEqual(config['build']['dockerfile'], 'Dockerfile')
        self.assertNotIn('dockerComposeFile', config)
        self.assertEqual(config['forwardPorts'], [5010])
        self.assertIn('ghcr.io/astral-sh/uv:0.10.8', (PROFILE / 'Dockerfile').read_text())


if __name__ == '__main__':
    unittest.main()
