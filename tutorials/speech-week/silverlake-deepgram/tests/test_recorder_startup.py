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
        async def converse(directory, clips, port, child):
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


    @unittest.skipUnless(Path("/proc/net/tcp").is_file(), "Linux kernel ownership evidence required")
    def test_foreign_ephemeral_peer_refused_with_live_nonlistening_child(self):
        import subprocess
        # The foreign socket takes the selected attempt port while the owned
        # child remains alive but has not bound it. No provider imports/calls.
        child = subprocess.Popen(["sleep", "30"], start_new_session=True)
        try:
            port = recorder.attempt_port()
            with socket.socket() as foreign:
                foreign.bind(("127.0.0.1", port))
                foreign.listen()
                with socket.create_connection(("127.0.0.1", port)) as client:
                    peer, _ = foreign.accept()
                    with peer, patch.object(recorder.os, "killpg") as kill:
                        with self.assertRaisesRegex(RuntimeError, "endpoint_not_owned_by_attempt"):
                            recorder.require_owned_connection(child, port)
                        self.assertIsNone(child.poll())
                        kill.assert_not_called()
                        # Ownership refusal precedes any protocol payload.
                        peer.settimeout(.05)
                        with self.assertRaises(socket.timeout):
                            peer.recv(1)
        finally:
            child.terminate()
            child.wait()


    @unittest.skipUnless(Path("/proc/net/tcp").is_file(), "Linux kernel ownership evidence required")
    def test_only_owned_connected_peer_can_receive_session_payload(self):
        import subprocess
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port)) as client:
                peer, _ = listener.accept()
                child = subprocess.Popen(["sleep", "30"], pass_fds=(peer.fileno(),), start_new_session=True)
                peer.close()
                try:
                    recorder.require_owned_connection(child, port)
                finally:
                    child.terminate()
                    child.wait()

    @unittest.skipUnless(Path("/proc/net/tcp").is_file(), "Linux kernel ownership evidence required")
    def test_conversation_sends_no_session_or_audio_to_foreign_peer(self):
        import asyncio
        import subprocess
        class Client:
            connected = False
            def on(self, name):
                return lambda handler: handler
            async def connect(self, *args, **kwargs):
                self.socket = socket.create_connection(("127.0.0.1", port))
                self.peer, _ = foreign.accept()
                self.connected = True
            async def emit(self, *args, **kwargs):
                raise AssertionError("no session or audio may reach a foreign peer")
            async def disconnect(self):
                self.socket.close()
                self.peer.close()
                self.connected = False
        child = subprocess.Popen(["sleep", "30"], start_new_session=True)
        try:
            with socket.socket() as foreign, tempfile.TemporaryDirectory() as directory:
                foreign.bind(("127.0.0.1", 0))
                foreign.listen()
                port = foreign.getsockname()[1]
                with patch.dict(recorder.sys.modules, {"socketio": SimpleNamespace(AsyncClient=lambda **kwargs: Client())}), \
                     patch.object(recorder.os, "killpg") as kill:
                    with self.assertRaisesRegex(RuntimeError, "endpoint_not_owned_by_attempt"):
                        asyncio.run(recorder.conversation(Path(directory), [b"fictional PCM"], port, child))
                    kill.assert_not_called()
                    self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait()
