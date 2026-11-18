"""Owner cleanup calls the two distinct Rasa lifecycle operations."""
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock

from shop_demo.assistant import Assistant


class AssistantCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_and_privacy_close_once(self):
        agent = Mock(close=AsyncMock())
        assistant = Assistant(object(), project=Path('.'), state_directory=Path('.'), clock=lambda: None)
        assistant.agent = agent
        await assistant.close()
        await assistant.close()
        agent.close.assert_awaited_once()
        agent.stop_privacy_manager.assert_called_once_with()
        self.assertIsNone(assistant.agent)

    async def test_runtime_failure_still_stops_owned_privacy_worker(self):
        agent = Mock(close=AsyncMock(side_effect=RuntimeError('synthetic close failure')))
        assistant = Assistant(object(), project=Path('.'), state_directory=Path('.'), clock=lambda: None)
        assistant.agent = agent
        with self.assertRaises(RuntimeError):
            await assistant.close()
        agent.stop_privacy_manager.assert_called_once_with()
        self.assertIsNone(assistant.agent)
