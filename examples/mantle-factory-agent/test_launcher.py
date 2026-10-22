"""Regression: SCRIPTED must run after setup without the optional LIVE worker.
sow: software-factories-masterclass-SOW-02
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
        values=dict(host='127.0.0.1',viewer_access='',viewer_name='',allow_peer=[],
                    builder_mode='SCRIPTED',worker_python='/absent/live-worker-python',
                    env_file=None,evidence_root='/unused',
                    expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
        values.update(changes)
        return Namespace(**values)

    def test_scripted_setup_uses_installed_project_interpreter(self):
        child=MagicMock();child.poll.return_value=None;child.pid=999999
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);python=root/'project-python';python.touch()
            with patch.object(launcher,'ROOT',root),patch.object(launcher,'PYTHON',python),patch.dict(os.environ,{'RASA_LICENSE':'synthetic-test-only'},clear=True),patch.object(launcher.socket,'socket'),patch.object(launcher.subprocess,'run') as train,patch.object(launcher.subprocess,'Popen',return_value=child),patch.object(launcher,'wait_ready'),patch.object(launcher.time,'sleep',side_effect=KeyboardInterrupt),patch.object(launcher.signal,'signal'),patch.object(launcher.os,'killpg'):
                train.return_value.returncode=0
                launcher.run(self.args())
                self.assertEqual(train.call_args.kwargs['env']['FACTORY_WORKER_PYTHON'],str(python))

    def test_live_without_worker_names_setup_live(self):
        with patch.object(launcher.socket,'socket'):
            with self.assertRaisesRegex(ValueError,'run ./demo setup-live first'):
                launcher.run(self.args(builder_mode='LIVE'))

if __name__=='__main__':unittest.main()
