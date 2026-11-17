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
import urllib.error
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
    'SHOP_OPERATOR_CHAT_ID': 'Send /start to your own bot, stop any running assistant, then run make chat-id. Save the printed private chat ID.',
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


def read_updates(token):
    return telegram_request(token, 'getUpdates', {'timeout': 0, 'limit': 100,
        'allowed_updates': ['message', 'edited_message', 'my_chat_member', 'callback_query']})


def read_identity(token):
    payload = telegram_request(token, 'getMe', {})
    if not isinstance(payload, dict) or payload.get('ok') is not True:
        raise ValueError('Telegram identity response shape')
    return payload.get('result')


def http_failure_hint(error):
    if error.code == 401:
        return 'Telegram rejected TELEGRAM_BOT_TOKEN. Copy the exact token from @BotFather, save it as a Codespace secret and restart the Codespace.'
    if error.code == 409:
        try:
            description = json.loads(error.read(8192)).get('description', '')
        except Exception:
            description = ''
        if isinstance(description, str) and 'webhook' in description.lower():
            return 'This bot has a webhook. Use a personal bot without a webhook, or review and remove that webhook before polling. No webhook was changed.'
        return 'Another reader may be polling this bot. Stop the other assistant or poller before running make chat-id.'
    if error.code == 429:
        return 'Telegram rate-limited the request. Wait before running make chat-id again.'
    return 'Telegram could not complete the request. Check the bot token and network; no update offset was advanced.'


def chat_id(environ=None, fetch=None, output=None, *, identify=None):
    environ = os.environ if environ is None else environ
    output = sys.stdout if output is None else output
    token = environ.get('TELEGRAM_BOT_TOKEN', '')
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        print('TELEGRAM_BOT_TOKEN: missing or invalid. Get the exact token from @BotFather; keep it private.', file=output)
        return 1
    try:
        with discovery_lock(environ.get('SHOP_STATE_DIR', '.state')):
            identity = BotIdentity.model_validate((read_identity if identify is None else identify)(token))
            print(f'Listening as @{identity.username}: send /start to this bot', file=output, flush=True)
            payload = (read_updates if fetch is None else fetch)(token)
        if not isinstance(payload, dict) or payload.get('ok') is not True or not isinstance(payload.get('result'), list):
            raise ValueError('Telegram response shape')
        chats, kinds = set(), set()
        known_kinds = {'message', 'edited_message', 'channel_post', 'edited_channel_post',
            'my_chat_member', 'chat_member', 'callback_query', 'inline_query', 'chosen_inline_result',
            'poll', 'poll_answer', 'message_reaction', 'message_reaction_count',
            'business_connection', 'business_message', 'edited_business_message', 'deleted_business_messages'}
        for update in payload['result']:
            if not isinstance(update, dict):
                kinds.add('other')
                continue
            observed = known_kinds.intersection(update)
            kinds.update(observed or {'other'})
            message = update.get('message', update.get('edited_message'))
            if not isinstance(message, dict) or not isinstance(message.get('text'), str) or not isinstance(message.get('chat'), dict):
                continue
            if message['chat'].get('type') != 'private':
                continue
            chat = PrivateChat.model_validate(message['chat'])
            chats.add(chat.id)
        if not chats:
            if payload['result']:
                print('Updates arrived, but none is a private text message. Kinds seen: ' + ', '.join(sorted(kinds)) + '. No message text or chat IDs are shown.', file=output)
            print('No private text message is available. Send /start to the bot named above in a private Telegram chat, then run make chat-id again. The assistant must be stopped.', file=output)
            return 1
        if len(chats) != 1:
            print('More than one private chat is present. Use a new personal bot for this example; no chat was selected.', file=output)
            return 1
        print('Your private chat ID: ' + str(chats.pop()), file=output)
        print('Save this number as SHOP_OPERATOR_CHAT_ID in personal Codespaces secrets; grant this repository access and restart the Codespace.', file=output)
        return 0
    except urllib.error.HTTPError as error:
        print(f'Telegram HTTP {error.code}: ' + http_failure_hint(error), file=output)
    except BlockingIOError:
        print('The assistant is running. Stop it with Ctrl-C before make chat-id; two Telegram readers must not overlap.', file=output)
    except Exception as error:
        # Provider exceptions can contain a token-bearing URL or response body.
        print('Chat discovery failed (' + safe_error_type(error) + '). Check the bot token, network and that no other process polls this bot. No update offset was advanced.', file=output)
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
        hint = 'Another assistant holds this state directory. Stop that process before restarting.'
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
