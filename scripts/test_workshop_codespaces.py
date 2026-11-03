"""Check the travel factory Codespaces profile and the readiness command without real SDK calls."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / '.devcontainer/travel-factory'
WORKSHOP = ROOT / 'workshops/software-factories-masterclass'
SECRETS = ('RASA_LICENSE', 'OPENAI_API_KEY', 'DEEPGRAM_API_KEY')


class TravelFactoryProfileTests(unittest.TestCase):
    def config(self):
        return json.loads((PROFILE / 'devcontainer.json').read_text())

    def test_workshop_profile_name(self):
        self.assertEqual(self.config()['name'], 'Rasa Travel Agent Factory')

    def test_profile_uses_the_image_ports_and_four_cores(self):
        config = self.config()
        self.assertEqual(config['build']['dockerfile'], 'Dockerfile')
        self.assertNotIn('dockerComposeFile', config)
        self.assertEqual(config['forwardPorts'], [5010])
        self.assertGreaterEqual(config['hostRequirements']['cpus'], 4)
        self.assertIn('ghcr.io/astral-sh/uv:0.10.8', (PROFILE / 'Dockerfile').read_text())

    def test_profile_asks_for_exactly_the_three_secrets(self):
        self.assertEqual(sorted(self.config()['secrets']), sorted(SECRETS))

    def test_installer_finds_both_locked_environments(self):
        install = (PROFILE / 'install.sh').read_text()
        self.assertIn('uv sync --locked', install)
        for project in ('env', 'env/builder'):
            for name in ('pyproject.toml', 'uv.lock'):
                self.assertTrue((WORKSHOP / project / name).is_file(), project + '/' + name)

    def test_locked_environments_are_not_ignored(self):
        result = subprocess.run(['git', 'check-ignore', 'workshops/software-factories-masterclass/env/uv.lock',
                                 'workshops/software-factories-masterclass/env/builder/uv.lock'],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.stdout, '')


class DoctorTests(unittest.TestCase):
    def doctor(self, **secrets):
        with tempfile.TemporaryDirectory() as home:
            environment = {'PATH': '/usr/bin:/bin', 'HOME': home}
            environment.update(secrets)
            result = subprocess.run(['/bin/bash', str(WORKSHOP / 'desk'), 'doctor'],
                                    env=environment, capture_output=True, text=True)
        return result.stdout + result.stderr

    def test_reports_presence_and_never_prints_a_value(self):
        output = self.doctor(**{name: 'fixture-' + name.lower() + '-sentinel' for name in SECRETS})
        for name in SECRETS:
            self.assertIn(name + ' present', output)
            self.assertNotIn('sentinel', output)

    def test_names_a_missing_secret(self):
        output = self.doctor(RASA_LICENSE='fixture-license-sentinel', OPENAI_API_KEY='fixture-model-sentinel')
        self.assertIn('DEEPGRAM_API_KEY missing', output)
        self.assertNotIn('sentinel', output)


if __name__ == '__main__':
    unittest.main()
