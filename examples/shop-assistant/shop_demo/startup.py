"""Explain local prerequisites and retire unbound Telegram chat discovery."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .activity import clear_activity
from .state import open_state

HELP = {
    'RASA_PRO_LICENSE': 'Get a free Developer Edition license at https://rasa.com/developer-edition and save the full license.',
    'OPENAI_API_KEY': 'Create a project API key at https://platform.openai.com/api-keys and save the key.',
    'TELEGRAM_BOT_TOKEN': 'In Telegram, ask @BotFather for /newbot, then save the token it gives you.',
    'GOOGLE_CLIENT_SECRETS_JSON': 'Enable the Google Sheets API, create a Desktop app OAuth client in Google Cloud, and save the complete downloaded JSON.',
    'GOOGLE_TOKEN_JSON': 'Run make google-signin, allow Sheets access, paste the final address at its prompt, then save the printed token JSON.',
    'SHOP_SHEET_ID': 'Create a dedicated blank Google Sheet. Copy only the identifier between /d/ and /edit in its browser address.',
    'SHOP_OPERATOR_CHAT_ID': 'Run make telegram, send its fresh setup code to your own bot, then choose session settings or save the confirmed private chat ID.',
}


class BotIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    username: str = Field(pattern=r"^[A-Za-z0-9_]{5,32}$")
    is_bot: Literal[True]


class PrivateChat(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True, hide_input_in_errors=True)
    id: StrictInt = Field(gt=0)
    type: str


def doctor(environ=None, output=None):
    environ = os.environ if environ is None else environ
    output = sys.stdout if output is None else output
    ok = True
    for name, hint in HELP.items():
        value = environ.get(name, '')
        valid = bool(value.strip())
        if name == 'SHOP_OPERATOR_CHAT_ID' and valid:
            valid = bool(re.fullmatch(r'[1-9][0-9]*', value))
        if name == 'SHOP_SHEET_ID' and valid:
            valid = bool(re.fullmatch(r'[A-Za-z0-9_-]{20,120}', value))
        print(f'{name}: {"SET" if valid else "MISSING or INVALID"}', file=output)
        if not valid:
            ok = False
            print('  ' + hint, file=output)
    if not ok:
        print('Save each named value in https://github.com/settings/codespaces, grant RasaHQ/rasa-community-resources access, then stop and start this Codespace. No values are printed by doctor.', file=output)
    return 0 if ok else 1


@contextmanager
def discovery_lock(directory):
    """Hold the same private SQLite lock as the launcher, even on first use."""
    path = Path(directory) / 'run.sqlite3'
    check = open_state(path)
    check.close()
    descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        clear_activity(directory)
        yield
    finally:
        os.close(descriptor)


def telegram_request(token, method, payload, *, timeout=15):
    request = urllib.request.Request('https://api.telegram.org/bot' + token + '/' + method,
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(1024 * 1024))


def chat_id(environ=None, fetch=None, output=None, *, identify=None):
    """Refuse the retired shortcut without reading or selecting queued senders."""
    output = sys.stdout if output is None else output
    print('Unchallenged chat discovery is retired. Run make telegram and send its fresh setup code to your own bot. No chat was selected or settings changed.', file=output)
    return 1


def safe_error_type(error):
    known = {'ValueError', 'ValidationError', 'RuntimeError', 'TimeoutError', 'ConnectionError',
             'HTTPError', 'URLError', 'PermissionError', 'FileNotFoundError', 'BlockingIOError',
             'ImportError', 'ModuleNotFoundError', 'OSError', 'Held', 'SheetFailure',
             'ShopError', 'TelegramError', 'McpError', 'StartupConfigurationError'}
    name = type(error).__name__
    return name if name in known else 'ProviderError'


def failure_hint(error):
    name = safe_error_type(error)
    if isinstance(error, BlockingIOError):
        hint = 'Another local command may briefly hold this state directory. Retry after make status finishes; if the lock remains busy, inspect the foreground assistant before restarting.'
    elif name == 'TelegramError':
        code = getattr(error, 'code', None)
        if getattr(error, 'retry_after_seconds', None) is not None:
            hint = 'Telegram rate-limited the request. Wait before restarting; preserve and inspect any uncertain send.'
        elif code == 'invalid_configuration':
            hint = 'Copy the exact token from BotFather and run make telegram; save it and restart if using Codespaces secrets.'
        elif code == 'provider_refused':
            hint = 'Run make status to check the bot token and webhook; stop any other reader. Preserve the original turn before restarting.'
        else:
            hint = 'Check the network and run make status. Preserve the original turn and inspect any uncertain send before restarting.'
    elif isinstance(error, (ImportError, FileNotFoundError)):
        hint = 'Run make setup to check the three locked environments, then make doctor.'
    elif isinstance(error, ValueError):
        hint = 'Run make doctor and correct the named settings. If it passes, inspect the preserved original turn before restarting.'
    else:
        hint = 'Check the connection and provider configuration. Preserve .state and inspect the original turn before restarting; do not repeat an uncertain order or send.'
    return f'Shop assistant stopped ({name}). {hint}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'chat-id'])
    command = parser.parse_args().command
    return doctor() if command == 'doctor' else chat_id()


if __name__ == '__main__':
    raise SystemExit(main())
