"""Startup ownership controls; no provider or model calls."""
import importlib.util
from pathlib import Path
import socket
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
