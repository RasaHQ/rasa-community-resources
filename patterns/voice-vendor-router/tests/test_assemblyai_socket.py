#!/usr/bin/env python3
"""The AssemblyAI socket must open on the websockets client Rasa pins.

The adapter called the legacy `websockets.connect(..., extra_headers=...)`.
On websockets 15.0.1, which rasa-pro 3.21.0.dev5 resolves to, that raised
`TypeError: BaseEventLoop.create_connection() got an unexpected keyword
argument 'extra_headers'` on every call, before a byte reached AssemblyAI.
The same bug was found live in the Speechmatics adapter by the case-build
pilot. No network beyond a refused localhost port, no credentials.
"""

from __future__ import annotations

import asyncio
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicerouter.failures import FailureKind, classify  # noqa: E402


class TestAssemblyAISocket(unittest.TestCase):
    def setUp(self):
        # The engine checks its key at construction; a placeholder is enough offline.
        patcher = mock.patch.dict("os.environ", {"ASSEMBLYAI_API_KEY": "test-key"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _engine(self, **config):
        from rasa.core.channels.voice_stream.audio_bytes import L16_16KHZ

        from voicerouter.providers.assemblyai import AssemblyAIASR

        return AssemblyAIASR.from_config_dict(
            {"language_map": {"en": {"language": "en"}}, **config}, L16_16KHZ, "en"
        )

    def test_connects_with_additional_headers_and_a_bare_key(self):
        from voicerouter.providers.assemblyai import DEFAULT_ENDPOINT

        with mock.patch(
            "voicerouter.providers.assemblyai.connect",
            new=mock.AsyncMock(return_value=mock.AsyncMock()),
        ) as connect:
            asyncio.run(self._engine().open_websocket_connection())
        url = connect.call_args.args[0]
        kwargs = connect.call_args.kwargs
        self.assertEqual(kwargs["additional_headers"], {"Authorization": "test-key"})
        self.assertNotIn("extra_headers", kwargs)
        self.assertTrue(url.startswith(DEFAULT_ENDPOINT + "?"))
        self.assertIn("encoding=pcm_s16le", url)
        self.assertIn("sample_rate=16000", url)

    def test_a_real_connect_reaches_the_network(self):
        # Unmocked: the legacy call raised TypeError here, before connecting.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        engine = self._engine(endpoint=f"ws://127.0.0.1:{port}/v3/ws")
        with self.assertRaises(OSError):
            asyncio.run(engine.open_websocket_connection())

    def test_a_rejected_key_is_logged_and_classified_as_auth(self):
        from websockets.datastructures import Headers
        from websockets.exceptions import InvalidStatus
        from websockets.http11 import Response

        rejected = InvalidStatus(Response(401, "Unauthorized", Headers()))
        with mock.patch(
            "voicerouter.providers.assemblyai.connect",
            new=mock.AsyncMock(side_effect=rejected),
        ):
            with self.assertRaises(InvalidStatus) as caught:
                asyncio.run(self._engine().open_websocket_connection())
        self.assertEqual(classify(caught.exception).kind, FailureKind.AUTH)


if __name__ == "__main__":
    unittest.main()
