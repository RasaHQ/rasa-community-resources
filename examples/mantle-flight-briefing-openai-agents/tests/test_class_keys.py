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
    return 'sk-' + ('ant-' if provider == 'anthropic' else 'proj-') + 'Q7m9V2x4N6p8R0t3W5y1Z9c7B4d2F6h8J0k3L5s1U9v7X4a2'


def assert_no_fragments(case, text, key):
    # Independent of the production detector/regex. Do not echo the canary
    # itself in an assertion diagnostic.
    if any(key[i:i + 8] in text for i in range(len(key) - 7)):
        case.fail('planted credential fragment escaped')


class ClassKeys(unittest.TestCase):
    def doctor(self, args=(), env=None):
        out = io.StringIO()
        with patch.dict(os.environ, env or {}, clear=True), contextlib.redirect_stdout(out):
            code = class_doctor.main(args)
        assert_no_fragments(self, out.getvalue(), fake_key())
        assert_no_fragments(self, out.getvalue(), fake_key('anthropic'))
        return code, out.getvalue()

    def test_doctor_no_keys_is_ready_scripted_but_explicit_live_refuses(self):
        code, text = self.doctor()
        self.assertEqual(code, 0)
        self.assertIn('OPENAI_API_KEY: MISSING', text)
        self.assertIn('ANTHROPIC_API_KEY: MISSING', text)
        self.assertIn('PATH: SCRIPTED', text)
        self.assertNotIn('Refused:', text)
        self.assertEqual(self.doctor(['--scripted'])[0], 0)
        for option in ('--probe', '--probe-agents'):
            self.assertEqual(self.doctor([option])[0], 2)

    def test_voice_readiness_is_value_free_and_never_selects_a_live_model(self):
        canary = 'synthetic-deepgram-Q7m9V2x4N6p8R0t3'
        with patch.object(class_doctor, 'probe_agents', side_effect=AssertionError('no call')), \
                patch.object(class_doctor, 'probe_mantle', side_effect=AssertionError('no call')):
            code, text = self.doctor(env={'DEEPGRAM_API_KEY': canary})
        self.assertEqual(code, 0)
        self.assertIn('DEEPGRAM_API_KEY: SET', text)
        self.assertIn('PATH: SCRIPTED', text)
        self.assertNotIn(canary, text)
        self.assertNotIn('Traceback', text)
        code, text = self.doctor()
        self.assertEqual(code, 0)
        self.assertIn('DEEPGRAM_API_KEY: MISSING', text)
        self.assertIn('continue with text', text)

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
        assert_no_fragments(self, out.getvalue(), fake_key())
        assert_no_fragments(self, out.getvalue(), fake_key('anthropic'))

    def test_uncaught_traceback_boundary_and_nested_card_transcript_values(self):
        install()
        key = fake_key('anthropic')
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            try:
                raise RuntimeError(key)
            except RuntimeError:
                sys.excepthook(*sys.exc_info())
        assert_no_fragments(self, out.getvalue(), fake_key())
        assert_no_fragments(self, out.getvalue(), fake_key('anthropic'))
        assert_no_fragments(self, json.dumps(redact({'cards': [{'source': key}], 'transcript': key})), key)

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
            self.assertEqual(code, 0)
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
            if any(key[i:i + 8] in text for i in range(len(key) - 7)):
                raise AssertionError('credential fragment output forbidden')
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
        assert_no_fragments(self, out.getvalue(), fake_key())
        assert_no_fragments(self, out.getvalue(), fake_key('anthropic'))

    def test_clipped_masked_and_escaped_key_output_is_redacted_independently(self):
        from project.lib.capability_logging import redact_api
        key = fake_key()
        with patch.dict(os.environ, {'OPENAI_API_KEY': key}, clear=True):
            for text in (key[13:], key[:25], 'invalid input=' + key[8:42],
                         'masked ***' + key[-4:], 'masked ...' + key[-4:],
                         'note' + chr(92) + 'n' + key, repr('note\n' + key)):
                with self.subTest(kind='synthetic-output'):
                    safe = redact_api(text)
                    assert_no_fragments(self, safe, key)
                    if text.startswith('masked'):
                        self.assertFalse(safe.endswith(key[-4:]), 'masked suffix escaped')
        # Shape redaction must also work without an environment key.
        with patch.dict(os.environ, {}, clear=True):
            assert_no_fragments(self, redact_api(repr('note\t' + key)), key)

    def test_short_or_blank_environment_values_do_not_rewrite_common_text(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ' the ', 'ANTHROPIC_API_KEY': ' '}, clear=True):
            self.assertEqual(redact('the weather is available'), 'the weather is available')

    @unittest.skipUnless(importlib.util.find_spec('rasa'), 'Mantle project interpreter required')
    def test_engine_bootstrap_subprocess_with_planted_dotenv(self):
        key = fake_key()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / '.env').write_text('OPENAI_API_KEY=' + key + '\n')
            script = "import os; os.environ['LITELLM_MODE']='PRODUCTION'; import litellm; from rasa.core.agent import Agent; assert 'OPENAI_API_KEY' not in os.environ; print('DOTENV_NOT_IMPORTED')"
            env = {k: v for k, v in os.environ.items() if k not in class_doctor.KEYS.values()}
            result = subprocess.run([sys.executable, '-c', script], cwd=p, env=env,
                                    capture_output=True, text=True, timeout=60)
            assert_no_fragments(self, result.stdout + result.stderr, key)
            self.assertEqual(result.returncode, 0, 'isolated engine dotenv control failed')
            self.assertIn('DOTENV_NOT_IMPORTED', result.stdout)
            self.assertEqual((p / '.env').read_text(), 'OPENAI_API_KEY=' + key + '\n')

    def test_short_key_and_custom_base_url_refuse_without_echo(self):
        code, text = self.doctor(env={'OPENAI_API_KEY': 'short'})
        self.assertEqual(code, 2)
        for name in ('OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL'):
            code, text = self.doctor(['--probe'], {'OPENAI_API_KEY': fake_key(), name: 'https://example.invalid/private'})
            self.assertEqual(code, 2)
            self.assertIn('base URL environment is SET', text)
            self.assertNotIn('example.invalid', text)
