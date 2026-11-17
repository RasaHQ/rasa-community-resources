"""Real locked Agent lifecycle in an owned child, with all network denied."""
import asyncio
from datetime import datetime, timezone
import faulthandler
import os
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch

from shop_demo.assistant import Assistant


async def check():
    project = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as directory:
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-never-a-real-key',
                'RASA_TELEMETRY_ENABLED': 'false', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}), \
                patch('rasa.utils.licensing.validate_license_from_env'), \
                patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
            async with Assistant(object(), project=project, state_directory=Path(directory),
                    clock=lambda: datetime.now(timezone.utc)) as assistant:
                manager = assistant.agent.privacy_manager
            if manager is not None:
                assert not manager.can_consume_from_tracker_queue
                assert not manager.background_scheduler.running


if __name__ == '__main__':
    asyncio.run(check())
    # A leaked worker now produces a stack, and the parent fails the control.
    # This is diagnostic only: it cannot force a successful process exit.
    faulthandler.dump_traceback_later(4)
    print('AGENT_CLOSE_COMPLETE', flush=True)
