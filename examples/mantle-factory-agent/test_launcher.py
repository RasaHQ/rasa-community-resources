"""Regression: SCRIPTED must run after setup without the optional LIVE worker.
"""
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import launcher

class InterpreterSelectionTests(unittest.TestCase):
    def args(self, **changes):
        values=dict(voice=False,host='127.0.0.1',viewer_access='',viewer_name='',allow_peer=[],
                    entry_port=8960,inspector_port=5020,mcp_port=8961,
                    builder_mode='SCRIPTED',worker_python='/absent/live-worker-python',
                    env_file=None,evidence_root='/unused',
                    expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
        values.update(changes)
        return Namespace(**values)

    def test_scripted_setup_uses_installed_project_interpreter(self):
        child=MagicMock();child.poll.return_value=None;child.pid=999999;child.stdout.readline.return_value=b''
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);python=root/'project-python';python.touch()
            with patch.object(launcher,'ROOT',root),patch.object(launcher,'PYTHON',python),patch.dict(os.environ,{'RASA_LICENSE':'synthetic-test-only'},clear=True),patch.object(launcher.socket,'socket'),patch.object(launcher.subprocess,'run') as train,patch.object(launcher.subprocess,'Popen',return_value=child),patch.object(launcher,'wait_ready'),patch.object(launcher.time,'sleep',side_effect=KeyboardInterrupt),patch.object(launcher.signal,'signal'),patch.object(launcher.os,'killpg'):
                train.return_value.returncode=0
                launcher.run(self.args())
                self.assertEqual(train.call_args.kwargs['env']['FACTORY_WORKER_PYTHON'],str(python))

    def test_voice_key_reaches_only_inspector_and_is_opt_in(self):
        child=MagicMock();child.poll.return_value=None;child.pid=999999;child.stdout.readline.return_value=b''
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);python=root/'project-python';python.touch()
            credentials=root/'owner.env';credentials.write_text('RASA_LICENSE=synthetic-license\nDEEPGRAM_API_KEY=synthetic-deepgram\nOPENAI_API_KEY=synthetic-model\n')
            for voice in (False, True):
                with self.subTest(voice=voice),patch.object(launcher,'ROOT',root),patch.object(launcher,'PYTHON',python),patch.dict(os.environ,{},clear=True),patch.object(launcher.socket,'socket'),patch.object(launcher.subprocess,'run') as train,patch.object(launcher.subprocess,'Popen',return_value=child) as spawn,patch.object(launcher,'wait_ready'),patch.object(launcher.time,'sleep',side_effect=KeyboardInterrupt),patch.object(launcher.signal,'signal'),patch.object(launcher.os,'killpg'):
                    train.return_value.returncode=0
                    launcher.run(self.args(voice=voice,env_file=str(credentials)))
                    self.assertNotIn('DEEPGRAM_API_KEY',train.call_args.kwargs['env'])
                    for call in spawn.call_args_list:
                        env=call.kwargs['env'];is_inspector='_inspector' in call.args[0]
                        self.assertEqual(env.get('DEEPGRAM_API_KEY'), 'synthetic-deepgram' if voice and is_inspector else None)
                        self.assertNotIn('OPENAI_API_KEY',env)

    def test_live_without_worker_names_setup_live(self):
        with patch.object(launcher.socket,'socket'):
            with self.assertRaisesRegex(ValueError,'run ./demo setup-live first'):
                launcher.run(self.args(builder_mode='LIVE'))

if __name__=='__main__':unittest.main()
