"""Synthetic credentials only: environment, config and public output boundaries."""
import contextlib
import io
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import class_doctor
from project.lib.capability_logging import install, redact, contains_api_key


def fake_key(provider='openai'):
    return 'sk-' + ('ant-' if provider == 'anthropic' else 'proj-') + 'syntheticOnly' * 4


class ClassKeys(unittest.TestCase):
    def doctor(self, args=(), env=None):
        out = io.StringIO()
        with patch.dict(os.environ, env or {}, clear=True), contextlib.redirect_stdout(out):
            code = class_doctor.main(args)
        self.assertFalse(contains_api_key(out.getvalue()))
        return code, out.getvalue()

    def test_doctor_missing_keys_refuses_and_names_scripted_fallback(self):
        code, text = self.doctor()
        self.assertEqual(code, 2)
        self.assertIn('OPENAI_API_KEY: MISSING', text)
        self.assertIn('ANTHROPIC_API_KEY: MISSING', text)
        self.assertIn('PATH: SCRIPTED', text)
        self.assertIn('Refused:', text)
        self.assertEqual(self.doctor(['--scripted'])[0], 0)

    def test_both_provider_settings_and_environment_only_readiness(self):
        for provider, variable in class_doctor.KEYS.items():
            with self.subTest(provider=provider), patch.object(class_doctor, 'selected_provider', return_value=provider):
                code, text = self.doctor(env={variable: fake_key(provider)})
                self.assertEqual(code, 0)
                self.assertIn('PATH: live ' + provider.upper(), text)
                self.assertIn(variable + ': SET', text)
                self.assertNotIn(fake_key(provider), text)

    def test_provider_failure_traceback_and_secret_are_not_printed(self):
        key = fake_key()
        with patch.object(class_doctor, 'probe_agents', side_effect=RuntimeError(key)):
            code, text = self.doctor(['--probe-agents'], {'OPENAI_API_KEY': key})
        self.assertEqual(code, 1)
        self.assertNotIn(key, text)
        self.assertNotIn('Traceback', text)

    def test_invalid_doctor_options_do_not_echo_pasted_credential(self):
        code, text = self.doctor(['--api-key', fake_key()])
        self.assertEqual(code, 2)
        self.assertIn('Refused:', text)
        self.assertFalse(contains_api_key(text))

    def test_formatted_logs_extra_and_exception_text_are_redacted(self):
        install()
        key = fake_key()
        out = io.StringIO()
        handler = logging.StreamHandler(out)
        handler.setFormatter(logging.Formatter('%(message)s %(extra_secret)s'))
        logger = logging.getLogger('class.keys.synthetic')
        logger.addHandler(handler)
        try:
            try:
                raise RuntimeError(key)
            except RuntimeError:
                logger.exception('synthetic %s', key, extra={'extra_secret': key})
        finally:
            logger.removeHandler(handler)
        self.assertFalse(contains_api_key(out.getvalue()))

    def test_uncaught_traceback_boundary_and_nested_card_transcript_values(self):
        install()
        key = fake_key('anthropic')
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            try:
                raise RuntimeError(key)
            except RuntimeError:
                sys.excepthook(*sys.exc_info())
        self.assertFalse(contains_api_key(out.getvalue()))
        self.assertFalse(contains_api_key(redact({'cards': [{'source': key}], 'transcript': key})))

    def test_dotenv_is_not_read_or_written_and_git_ignores_key_files(self):
        key = fake_key()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / '.env').write_text('OPENAI_API_KEY=' + key)
            before = {x.name: x.read_bytes() for x in p.iterdir()}
            previous = Path.cwd()
            try:
                os.chdir(p)
                code, text = self.doctor()
            finally:
                os.chdir(previous)
            self.assertEqual(code, 2)
            self.assertIn('OPENAI_API_KEY: MISSING', text)
            self.assertEqual(before, {x.name: x.read_bytes() for x in p.iterdir()})
        repo = ROOT.parents[1]
        # The finite qualification receives a git archive, not .git metadata.
        # Exercise Git's real ignore semantics in an owned scratch repository
        # using the exact shipped root ignore file; do not skip this check.
        with tempfile.TemporaryDirectory() as git_tmp:
            subprocess.run(['git', 'init', '-q', git_tmp], capture_output=True, check=True)
            (Path(git_tmp) / '.gitignore').write_bytes((repo / '.gitignore').read_bytes())
            result = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=git_tmp,
                input='\n'.join(str(ROOT.relative_to(repo) / name) for name in ('.env', '.env.local', '.envrc', 'private.key')) + '\n',
                text=True, capture_output=True, check=True)
        self.assertEqual(len(result.stdout.splitlines()), 4)
        tracked = subprocess.run(['git', 'ls-files', str(ROOT.relative_to(repo))], cwd=repo,
                                 text=True, capture_output=True)
        files = ([repo / name for name in tracked.stdout.splitlines()] if tracked.returncode == 0 else
                 [p for p in ROOT.rglob('*') if p.is_file() and
                  not {'.venv', '__pycache__'}.intersection(p.relative_to(ROOT).parts)])
        for source in files:
            self.assertNotIn(key.encode(), source.read_bytes())

    def test_selected_provider_config_is_one_setting_with_env_references(self):
        self.assertEqual(class_doctor.selected_provider(), 'openai')
        text = (ROOT / 'project/integrations.yml').read_text()
        self.assertIn('api_key: ${OPENAI_API_KEY}', text)
        self.assertIn('api_key: ${ANTHROPIC_API_KEY}', text)
        self.assertNotIn('oauth', text.lower())
        self.assertFalse(contains_api_key(text))

    @unittest.skipUnless(importlib.util.find_spec('rasa'), 'Mantle project interpreter required')
    def test_installed_engine_resolves_both_provider_groups_without_key_files(self):
        from rasa.core.agent import Agent
        from rasa.mantle.model_archive.bootstrap import resolve_integration_llm_config
        text = (ROOT / 'project/integrations.yml').read_text()
        for provider, name in class_doctor.KEYS.items():
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)
                (p / 'integrations.yml').write_text(text.replace('model_group: openai', 'model_group: ' + provider))
                with patch.dict(os.environ, {name: fake_key(provider)}, clear=True):
                    config = resolve_integration_llm_config(p)
                self.assertEqual(config['models'][0]['provider'], provider)
                self.assertNotIn(fake_key(provider), (p / 'integrations.yml').read_text())

    def test_key_shapes_in_an_output_artifact_are_a_failing_condition(self):
        key = fake_key()
        def check_output(text):
            if contains_api_key(text):
                raise AssertionError('credential-shaped output forbidden')
        with self.assertRaises(AssertionError):
            check_output('transcript ' + key)
        check_output(redact('transcript ' + key))
        check_output('desk-widgets-companion is a resource directory, not a key')

    @unittest.skipUnless(importlib.util.find_spec('structlog'), 'Mantle project interpreter required')
    def test_structured_late_exception_values_are_redacted_after_rendering(self):
        import structlog
        install()
        key = fake_key('anthropic')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                raise RuntimeError(key)
            except RuntimeError:
                structlog.get_logger('class.synthetic').exception('failure', data={'key': key})
        self.assertFalse(contains_api_key(out.getvalue()))
