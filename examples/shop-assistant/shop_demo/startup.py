"""Explain local prerequisites and discover one private Telegram chat."""
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

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .state import open_state

HELP = {
    'RASA_PRO_LICENSE': 'Get a free Developer Edition license at https://rasa.com/developer-edition and save the full license.',
    'OPENAI_API_KEY': 'Create a project API key at https://platform.openai.com/api-keys and save the key.',
    'TELEGRAM_BOT_TOKEN': 'In Telegram, ask @BotFather for /newbot, then save the token it gives you.',
    'GOOGLE_CLIENT_SECRETS_JSON': 'Enable the Google Sheets API, create a Desktop app OAuth client in Google Cloud, and save the complete downloaded JSON.',
    'GOOGLE_TOKEN_JSON': 'Run make google-signin, allow Sheets access, paste the final address at its prompt, then save the printed token JSON.',
    'SHOP_SHEET_ID': 'Create a dedicated blank Google Sheet. Copy only the identifier between /d/ and /edit in its browser address.',
    'SHOP_OPERATOR_CHAT_ID': 'Send /start to your own bot, stop any running assistant, then run make chat-id. Save the printed private chat ID.',
}


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
        yield
    finally:
        os.close(descriptor)


def read_updates(token):
    request = urllib.request.Request('https://api.telegram.org/bot' + token + '/getUpdates',
        data=b'{"timeout":0,"limit":100}', headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read(1024 * 1024))


def chat_id(environ=None, fetch=None, output=None):
    environ = os.environ if environ is None else environ
    output = sys.stdout if output is None else output
    token = environ.get('TELEGRAM_BOT_TOKEN', '')
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        print('TELEGRAM_BOT_TOKEN: missing or invalid. Get the exact token from @BotFather; keep it private.', file=output)
        return 1
    try:
        with discovery_lock(environ.get('SHOP_STATE_DIR', '.state')):
            payload = (read_updates if fetch is None else fetch)(token)
        if not isinstance(payload, dict) or payload.get('ok') is not True or not isinstance(payload.get('result'), list):
            raise ValueError('Telegram response shape')
        chats = set()
        for update in payload['result']:
            if not isinstance(update, dict):
                continue
            message = update.get('message')
            if not isinstance(message, dict) or not isinstance(message.get('chat'), dict):
                continue
            if message['chat'].get('type') != 'private':
                continue
            chat = PrivateChat.model_validate(message['chat'])
            chats.add(chat.id)
        if not chats:
            print('No private message has arrived yet. Send /start to your own bot in Telegram, then run make chat-id again. The assistant must be stopped.', file=output)
            return 1
        if len(chats) != 1:
            print('More than one private chat is present. Use a new personal bot for this example; no chat was selected.', file=output)
            return 1
        print('Your private chat ID: ' + str(chats.pop()), file=output)
        print('Save this number as SHOP_OPERATOR_CHAT_ID in personal Codespaces secrets; grant this repository access and restart the Codespace.', file=output)
        return 0
    except BlockingIOError:
        print('The assistant is running. Stop it with Ctrl-C before make chat-id; two Telegram readers must not overlap.', file=output)
    except Exception as error:
        # Provider exceptions can contain a token-bearing URL or response body.
        print('Chat discovery failed (' + safe_error_type(error) + '). Check the bot token, network and that no other process polls this bot. No update offset was advanced.', file=output)
    return 1


def safe_error_type(error):
    known = {'ValueError', 'ValidationError', 'RuntimeError', 'TimeoutError', 'ConnectionError',
             'HTTPError', 'URLError', 'PermissionError', 'FileNotFoundError', 'BlockingIOError',
             'ImportError', 'ModuleNotFoundError', 'OSError'}
    name = type(error).__name__
    return name if name in known else 'ProviderError'


def failure_hint(error):
    name = safe_error_type(error)
    if isinstance(error, BlockingIOError):
        hint = 'Another assistant holds this state directory. Stop that process before restarting.'
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
