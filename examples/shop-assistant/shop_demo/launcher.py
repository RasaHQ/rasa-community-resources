"""Run one bounded operator conversation, then close all owned clients."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import signal
import sys

from .activity import assistant_activity
from .assistant import Assistant
from .conversation import Conversation
from .mcp_client import ShopClient
from .settings import Settings
from .state import open_state
from .startup import failure_hint
from .telegram_poll import POLL_TYPES, poll_updates


class StartupConfigurationError(ValueError):
    """An actionable configuration failure whose message contains no inputs."""


def telegram_client(token):
    from zeo_integrations.telegram.direct import TelegramClient, TelegramError
    try:
        return TelegramClient(token)
    except TelegramError as error:
        if error.code == "invalid_configuration":
            raise StartupConfigurationError(
                "TELEGRAM_BOT_TOKEN was rejected. Save the exact BotFather token "
                "as a Codespace secret, then restart the Codespace."
            ) from None
        raise


async def drive(conversation, telegram, stop, *, max_turns=30, seconds=900):
    conversation.assert_restart_safe()
    deadline = asyncio.get_running_loop().time() + seconds
    turns = 0
    while not stop.is_set() and turns < max_turns and asyncio.get_running_loop().time() < deadline:
        saved = conversation.saved()
        if not saved:
            updates = await poll_updates(telegram, offset=conversation.offset(), limit=20, timeout=10,
                    allowed_updates=POLL_TYPES)
            conversation.retain([update.raw_payload for update in updates])
            for update in updates:
                if update.unsupported_reason is not None:
                    conversation.quarantine(update.raw_payload)
            saved = conversation.saved()
        for original in saved:
            if stop.is_set() or turns >= max_turns or asyncio.get_running_loop().time() >= deadline:
                break
            await conversation.handle(original)
            turns += 1
        if not stop.is_set():
            await conversation.notify_shipments()
    return turns


async def run():
    settings = Settings.environment()
    project = Path(__file__).resolve().parent.parent
    server_python = project / "server" / ".venv" / "bin" / "python"
    if not server_python.is_file():
        raise ValueError("Install the locked server environment first")
    # Create and validate private state before acquiring the process lock.
    check = open_state(settings.state_directory / "run.sqlite3")
    check.close()
    lock = os.open(settings.state_directory / "run.sqlite3", os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        # Repeated signals only request a stop. They cannot interrupt cleanup.
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        try:
            child_env = {name: os.environ[name] for name in ("PATH", "LANG", "HOME", "SSL_CERT_FILE") if name in os.environ}
            child_env.update(GOOGLE_TOKEN_JSON=settings.google_token_json.get_secret_value(),
                SHOP_SHEET_ID=settings.spreadsheet_id, SHOP_STATE_DIR=str(settings.state_directory),
                PYTHONDONTWRITEBYTECODE="1")
            clock = lambda: datetime.now(timezone.utc)
            async with AsyncExitStack() as stack:
                telegram = await stack.enter_async_context(telegram_client(settings.telegram_token))
                client = await stack.enter_async_context(ShopClient(str(server_python),
                    arguments=["-B", "-m", "shop_demo.server"], environment=child_env, directory=project))
                assistant = await stack.enter_async_context(Assistant(client, project=project,
                    state_directory=settings.state_directory, clock=clock))
                conversation = Conversation(settings.state_directory / "conversation.sqlite3",
                    chat_id=settings.operator_chat_id, telegram=telegram, assistant=assistant, orders=client, clock=clock)
                stack.callback(conversation.close)
                with assistant_activity(settings.state_directory, settings.telegram_token.get_secret_value(), settings.operator_chat_id):
                    print("Shop assistant ready for the configured private chat. Ctrl-C requests a clean stop.", flush=True)
                    turns = await drive(conversation, telegram, stop, max_turns=settings.max_turns)
                print(f"Shop assistant stopped after {turns} retained updates.", flush=True)
        finally:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
    finally:
        os.close(lock)


def main():
    try:
        asyncio.run(run())
    except StartupConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Shop assistant stopped by keyboard. Preserve .state before restarting.", file=sys.stderr)
        return 1
    except Exception as error:
        print(failure_hint(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
