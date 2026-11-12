"""Owned-process shutdown controls; no model, speech or vendor connection."""
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from launcher import cleanup


class CleanupTests(unittest.TestCase):
    def test_signal_during_cleanup_does_not_skip_release(self):
        script='''import fcntl,os,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
import launcher
p=Path(sys.argv[1]);fd=os.open(p/'lease',os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(fd,fcntl.LOCK_EX)
def interrupted(*_):raise KeyboardInterrupt()
signal.signal(signal.SIGINT,interrupted)
def stop(_):print('cleanup_begin',flush=True);time.sleep(.5)
def close():os.close(fd);(p/'released').write_text('closed')
launcher.stop_child=stop
try:
 print('running',flush=True)
 while True:time.sleep(.05)
except KeyboardInterrupt:pass
finally:
 failed=launcher.cleanup(None,[],[],None,SimpleNamespace(close=close),{signal.SIGINT:interrupted})
print('cleanup_complete',flush=True)
raise SystemExit(bool(failed))
'''
        with tempfile.TemporaryDirectory() as temporary:
            child=subprocess.Popen([sys.executable,'-c',script,temporary],cwd=Path(__file__).resolve().parents[1],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(),'running')
                child.send_signal(signal.SIGINT)
                self.assertEqual(child.stdout.readline().strip(),'cleanup_begin')
                child.send_signal(signal.SIGINT)
                out,err=child.communicate(timeout=5)
                self.assertEqual(child.returncode,0,err)
                self.assertIn('cleanup_complete',out)
                self.assertTrue((Path(temporary)/'released').is_file())
                fd=os.open(Path(temporary)/'lease',os.O_RDWR)
                try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                finally:os.close(fd)
            finally:
                if child.poll() is None:child.kill();child.communicate()

    def test_child_stop_error_still_closes_state_and_journal(self):
        closed=[]
        with patch('launcher.stop_child',side_effect=ValueError('fictional failure')):
            failed=cleanup(None,[],[],SimpleNamespace(close=lambda:closed.append('state')),SimpleNamespace(close=lambda:closed.append('journal')), {})
        self.assertEqual(closed,['state','journal'])
        self.assertEqual(failed,['child'])

    def test_server_without_started_thread_is_closed_without_shutdown_wait(self):
        closed=[]
        def not_started():raise AssertionError('shutdown would wait forever')
        server=SimpleNamespace(shutdown=not_started,server_close=lambda:closed.append('server'))
        self.assertEqual(cleanup(None,[server],[],None,None,{}),[])
        self.assertEqual(closed,['server'])
