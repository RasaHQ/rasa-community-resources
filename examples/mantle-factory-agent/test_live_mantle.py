"""Live orchestration custody and credential-redaction controls.
sow: software-factories-masterclass-SOW-02
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import io
import os
import unittest
from unittest.mock import MagicMock, patch
import test_launcher
import launcher

class LiveMantleTests(unittest.TestCase):
    def test_only_inspector_receives_live_orchestrator_key(self):
        child=MagicMock();child.poll.return_value=None;child.pid=999999;child.stdout.readline.return_value=b''
        with TemporaryDirectory() as directory:
            root=Path(directory);python=root/'project-python';python.touch()
            credentials=root/'owner.env';credentials.write_text('RASA_LICENSE=synthetic-license\nDEEPGRAM_API_KEY=synthetic-deepgram\nOPENAI_API_KEY=synthetic-model\n')
            args=test_launcher.InterpreterSelectionTests().args(voice=True,mantle_mode='LIVE',env_file=str(credentials))
            with patch.object(launcher,'ROOT',root),patch.object(launcher,'PYTHON',python),patch.dict(os.environ,{},clear=True),patch.object(launcher.socket,'socket'),patch.object(launcher.subprocess,'run') as train,patch.object(launcher.subprocess,'Popen',return_value=child) as spawn,patch.object(launcher,'wait_ready'),patch.object(launcher.time,'sleep',side_effect=KeyboardInterrupt),patch.object(launcher.signal,'signal'),patch.object(launcher.os,'killpg'),patch.object(launcher.threading,'Thread'):
                train.return_value.returncode=0
                launcher.run(args)
                self.assertNotIn('OPENAI_API_KEY',train.call_args.kwargs['env'])
                for call in spawn.call_args_list:
                    env=call.kwargs['env'];inspector='_inspector' in call.args[0]
                    self.assertEqual(env.get('OPENAI_API_KEY'),'synthetic-model' if inspector else None)
                    self.assertEqual(env.get('DEEPGRAM_API_KEY'),'synthetic-deepgram' if inspector else None)
                    self.assertEqual(env['FACTORY_MANTLE_MODE'],'LIVE')
    def test_log_never_records_key_or_eight_character_fragment(self):
        secret='synthetic-live-model-key'
        child=MagicMock();child.stdout=io.BytesIO((secret+' '+secret[3:11]+'\n').encode());log=io.BytesIO()
        launcher.capture_log(child,log,{'OPENAI_API_KEY':secret})
        self.assertNotIn(secret.encode(),log.getvalue());self.assertNotIn(secret[3:11].encode(),log.getvalue())

class LiveBannerTests(unittest.TestCase):
    def test_live_mantle_with_scripted_builder_does_not_claim_live_build(self):
        from server import frontend
        from starlette.testclient import TestClient
        with patch.dict(os.environ, {'FACTORY_ALLOWED_PEERS':'testclient','FACTORY_MANTLE_MODE':'LIVE','FACTORY_BUILDER_MODE':'SCRIPTED'}, clear=True):
            page=TestClient(frontend('127.0.0.1')).get('/')
            self.assertIn('Live Mantle agent (OpenAI model)',page.text)
            self.assertIn('SCRIPTED builder with supplied attempts',page.text)
            self.assertNotIn('live builder on the OpenAI Agents API',page.text)
