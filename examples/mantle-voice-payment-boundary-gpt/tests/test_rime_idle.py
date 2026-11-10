"""Offline checks for the Rime idle reconnect. Needs the project's venv (it imports Rasa); skipped otherwise.

    uv run --locked python -m unittest tests.test_rime_idle -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

try:
    os.environ.setdefault("RIME_API_KEY", "offline-test")
    from engines import rime_idle
    from rasa.core.channels.voice_stream.audio_bytes import L16_16KHZ
except ImportError:  # plain python3 without the project's venv
    rime_idle = None


class FakeWS:
    def __init__(self) -> None:
        self.closed = False
        self.sent: list = []

    async def send_json(self, data) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True


@unittest.skipIf(rime_idle is None, "Rasa is not importable; run with the project's venv")
class RimeIdleTests(unittest.TestCase):
    def engine(self):
        engine = rime_idle.RimeTTSReconnectOnIdle.from_config_dict(
            {"model_id": "mistv3", "language_map": {"en": {"voice": "lagoon", "language": "en"}}}, L16_16KHZ, "en")
        self.opened = 0

        async def fake_connect(config=None):
            self.opened += 1
            engine.ws = FakeWS()
            engine._touch()

        engine.connect = fake_connect
        return engine

    def test_is_the_built_in_engine_with_its_config(self):
        engine = self.engine()
        self.assertIsInstance(engine, rime_idle.RimeTTS)
        self.assertEqual((engine.config.model_id, engine.current_language_config.voice), ("mistv3", "lagoon"))

    def test_fresh_socket_is_kept(self):
        engine = self.engine()
        asyncio.run(engine.connect())
        asyncio.run(engine.prepare_response())
        self.assertEqual(self.opened, 1)

    def test_idle_socket_is_reopened_before_the_next_response(self):
        engine = self.engine()
        asyncio.run(engine.connect())
        engine._last_traffic -= rime_idle.IDLE_RECONNECT_S + 1
        asyncio.run(engine.prepare_response())
        self.assertEqual(self.opened, 2)
        self.assertFalse(engine.ws.closed)

    def test_closed_socket_is_reopened(self):
        engine = self.engine()
        asyncio.run(engine.connect())
        engine.ws.closed = True
        self.assertTrue(engine.needs_reconnect())

    def test_sending_text_counts_as_traffic(self):
        engine = self.engine()
        asyncio.run(engine.connect())
        engine._last_traffic -= rime_idle.IDLE_RECONNECT_S + 1
        engine._active_response = type("R", (), {"response_id": "r1"})()
        asyncio.run(engine.send_text_chunk("Hello."))
        self.assertFalse(engine.needs_reconnect())


if __name__ == "__main__":
    unittest.main()
