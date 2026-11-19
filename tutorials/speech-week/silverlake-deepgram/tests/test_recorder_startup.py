"""Startup ownership controls; no provider or model calls."""
import importlib.util
from pathlib import Path
import socket
import contextlib
import io
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch, MagicMock

spec = importlib.util.spec_from_file_location("recorder", Path(__file__).resolve().parents[1] / "record_voice_once.py")
recorder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorder)


class RecorderStartup(unittest.TestCase):
    def test_existing_listener_refuses_before_caller_generation(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            with self.assertRaises(OSError):
                recorder.require_free_port(listener.getsockname()[1])

    def test_dead_child_cannot_accept_some_other_server(self):
        process = SimpleNamespace(poll=Mock(return_value=1))
        with patch.object(recorder.urllib.request, "urlopen") as request:
            self.assertFalse(recorder.owned_server_ready(process, "http://localhost"))
            request.assert_not_called()

    def test_child_exit_during_probe_is_not_ready(self):
        process = SimpleNamespace(poll=Mock(side_effect=[None, 1]))
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.object(recorder.urllib.request, "urlopen", return_value=response):
            self.assertFalse(recorder.owned_server_ready(process, "http://localhost"))

    def test_attempt_port_is_used_by_child_probe_and_client(self):
        async def synthesize(_): return []
        async def converse(directory, clips, port):
            self.assertEqual(port, 58412)
            return {"test_fixture": True}
        with tempfile.TemporaryDirectory() as directory:
            process = SimpleNamespace(poll=Mock(side_effect=[None, 0]), pid=123)
            with patch.object(recorder.sys, "argv", ["record", "--state-dir", directory]), \
                 patch.object(recorder, "require_free_port"), \
                 patch.object(recorder, "attempt_port", return_value=58412), \
                 patch.object(recorder, "synthesize", synthesize), \
                 patch.object(recorder, "conversation", converse), \
                 patch.object(recorder.subprocess, "Popen", return_value=process) as start, \
                 patch.object(recorder, "owned_server_ready", return_value=True) as ready, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(recorder.main(), 0)
                self.assertEqual(start.call_args.args[0][-2:], ["--port", "58412"])
                ready.assert_called_once_with(process, "http://127.0.0.1:58412/")

    def test_foreign_listener_refuses_without_generating_audio_or_killing_it(self):
        with socket.socket() as foreign, tempfile.TemporaryDirectory() as directory:
            try:
                foreign.bind(("127.0.0.1", 5005))
            except OSError:
                self.skipTest("port 5005 is already owned; test cannot reserve its foreign listener")
            foreign.listen()
            with patch.object(recorder.sys, "argv", ["record", "--state-dir", directory]), \
                 patch.object(recorder, "synthesize") as synthesize, \
                 patch.object(recorder.subprocess, "Popen") as start, \
                 patch.object(recorder.os, "killpg") as kill, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(recorder.main(), 1)
                synthesize.assert_not_called()
                start.assert_not_called()
                kill.assert_not_called()
            self.assertEqual(foreign.getsockname()[1], 5005)

    def test_first_run_schedules_verified_public_archive_before_server(self):
        import subprocess
        here = Path(__file__).resolve().parents[1]
        for target in ("run", "text"):
            result = subprocess.run(["make", "--dry-run", target], cwd=here,
                                    text=True, capture_output=True, check=True)
            self.assertIn("TPG_R2026.1.00_XSD.zip", result.stdout)
            self.assertLess(result.stdout.index("curl -fsSL"), result.stdout.index("python run_demo.py"))
            self.assertIn("sha256sum", result.stdout)

    def test_doctor_target_exists_without_scheduling_download(self):
        import subprocess
        here = Path(__file__).resolve().parents[1]
        result = subprocess.run(["make", "--dry-run", "doctor"], cwd=here,
                                text=True, capture_output=True, check=True)
        self.assertIn("python doctor_profile.py", result.stdout)
        self.assertNotIn("curl", result.stdout)
