"""Guide a student to their own bot and report safe, read-only status."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import warnings

from pydantic import BaseModel, ConfigDict, SecretStr

from .activity import local_activity
from .startup import BotIdentity, PrivateChat, discovery_lock, telegram_request


class Token(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, hide_input_in_errors=True)
    value: SecretStr

    def checked(self):
        value = self.value.get_secret_value()
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', value):
            raise ValueError('Invalid Telegram token')
        return value


class Webhook(BaseModel):
    model_config = ConfigDict(extra='ignore', strict=True, hide_input_in_errors=True)
    url: SecretStr


class PrivateTerminalRequired(Exception):
    """Hidden input cannot safely fall back to an echoed stream."""


class TelegramProblem(Exception):
    def __init__(self, code=None, webhook=False):
        super().__init__('Telegram check did not complete')
        self.code, self.webhook = code, webhook


def problem_hint(error):
    if isinstance(error, PrivateTerminalRequired):
        return 'Private input needs an interactive terminal. Open the Codespace Terminal tab and run make telegram there.'
    if isinstance(error, TelegramProblem):
        if error.code == 401:
            return 'Telegram rejected the token. Copy the exact token from @BotFather, then run make telegram again.'
        if error.code == 409 and error.webhook:
            return 'This bot has a webhook. Use a new personal bot, or ask its owner to remove the webhook; setup changed nothing.'
        if error.code == 409:
            return 'Another process may be reading this bot. Stop its foreground assistant with Ctrl-C, or use a different personal bot, then run make telegram.'
        if error.code == 429:
            return 'Telegram needs a pause. Wait a minute, then run make telegram again.'
    return 'The Telegram check could not finish. Check the connection and token, then run make telegram again; no update offset was advanced.'


def api(token, method, payload, *, timeout=15):
    """Reuse the setup transport; never expose its token-bearing errors."""
    try:
        response = telegram_request(token, method, payload, timeout=timeout)
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read(8192))
            webhook = isinstance(body, dict) and isinstance(body.get('description'), str) and 'webhook' in body['description'].lower()
        except Exception:
            webhook = False
        raise TelegramProblem(error.code, webhook) from None
    if not isinstance(response, dict):
        raise TelegramProblem()
    if response.get('ok') is not True:
        description = response.get('description', '')
        raise TelegramProblem(response.get('error_code'), isinstance(description, str) and 'webhook' in description.lower())
    return response.get('result')


def hidden_token(prompt):
    if not sys.stdin.isatty():
        raise PrivateTerminalRequired()
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            return getpass.getpass(prompt)
        except getpass.GetPassWarning:
            raise PrivateTerminalRequired() from None


def session_shell(environ):
    # Do not source user shell files or inherit shell tracing controls. The
    # token is in the child environment only, never its argv or shell history.
    clean = {key: value for key, value in environ.items()
             if key not in {'SHELLOPTS', 'BASHOPTS', 'BASH_ENV', 'ENV', 'PS4', 'PROMPT_COMMAND'}
             and not key.startswith('BASH_FUNC_')}
    clean['PS1'] = 'shop-session> '
    return subprocess.run(['/bin/bash', '--noprofile', '--norc', '-i'], env=clean, check=False).returncode


def private_chats(updates):
    if not isinstance(updates, list):
        raise TelegramProblem()
    chats = set()
    for update in updates:
        if not isinstance(update, dict):
            continue
        message = update.get('message', update.get('edited_message'))
        if (not isinstance(message, dict) or not isinstance(message.get('text'), str)
                or not isinstance(message.get('chat'), dict) or message['chat'].get('type') != 'private'):
            continue
        chats.add(PrivateChat.model_validate(message['chat']).id)
    return chats


def guided(environ=None, *, request=api, ask=input, secret=hidden_token,
           clock=time.monotonic, sleep=time.sleep, shell=session_shell, output=None, seconds=90):
    environ = dict(os.environ if environ is None else environ)
    output = sys.stdout if output is None else output
    def say(text):
        print(text, file=output, flush=True)
    say('Step 1: create your own bot. Open Telegram and search for the verified @BotFather.')
    say('Tap Start, send /newbot, choose a display name, then a unique username ending in bot.')
    say('Keep its token private. Use a separate bot for each Codespace so they do not compete for messages.')
    try:
        value = environ.get('TELEGRAM_BOT_TOKEN', '')
        if value:
            choice = ask('Use TELEGRAM_BOT_TOKEN already set here? [yes/no]: ').strip().lower()
            if choice not in {'yes', 'no'}:
                say('Setup paused. Run make telegram and answer yes or no; no settings changed.')
                return 1
            if choice == 'no':
                value = secret('Paste the BotFather token (hidden): ')
        else:
            value = secret('Paste the BotFather token (hidden): ')
        try:
            token = Token(value=SecretStr(value)).checked()
        except Exception:
            say('TELEGRAM_BOT_TOKEN is missing or invalid. Copy the exact token from @BotFather and run make telegram again.')
            return 1
        say('Step 2: checking which bot owns the token...')
        identity = BotIdentity.model_validate(request(token, 'getMe', {}))
        say(f'This is @{identity.username}. Open https://t.me/{identity.username} in Telegram.')
        say('Step 3: checking whether Telegram sends this bot to a webhook...')
        webhook = Webhook.model_validate(request(token, 'getWebhookInfo', {}))
        if webhook.url.get_secret_value():
            say(problem_hint(TelegramProblem(409, True)))
            return 1
        say('No webhook is configured. A remote reader cannot be ruled out; stop other Codespaces using this bot.')
        say('Setup can recognize edited text; the current assistant receives new messages and callbacks only. An edit cannot confirm an order.')
        say('Step 4: checking for your private message. Open the named bot and send /start now.')
        say(f'Waiting up to {seconds} seconds. Press Ctrl-C to leave setup; the assistant will not start automatically.')
        deadline = clock() + seconds
        chats = set()
        with discovery_lock(environ.get('SHOP_STATE_DIR', '.state')):
            while clock() < deadline:
                updates = request(token, 'getUpdates', {'timeout': 0, 'limit': 100,
                    'allowed_updates': ['message', 'edited_message', 'my_chat_member', 'callback_query']},
                    timeout=min(15, max(0.1, deadline - clock())))
                chats.update(private_chats(updates))
                if chats:
                    break
                sleep(min(2, max(0, deadline - clock())))
        if not chats:
            say('No private text message arrived. Send /start to the named bot, then run make telegram again. Group and membership updates do not select a chat.')
            return 1
        if len(chats) != 1:
            say('More than one private chat is present. Use a fresh personal bot, then run make telegram; no chat was selected.')
            return 1
        chat = str(chats.pop())
        say('Your private chat ID: ' + chat)
        say('Step 5: choose where your settings live.')
        say('Persistent: open https://github.com/settings/codespaces; add TELEGRAM_BOT_TOKEN and SHOP_OPERATOR_CHAT_ID, grant this repository access, then stop and start the Codespace.')
        say('For this class: open a shop-session shell with these two settings in memory. Run make doctor, make status or make run there; exit ends the session. Your original terminal is unchanged.')
        choice = ask('Open the session shell now? [yes/no]: ').strip().lower()
        if choice == 'yes':
            environ.update(TELEGRAM_BOT_TOKEN=token, SHOP_OPERATOR_CHAT_ID=chat)
            say('Opening shop-session. No credential file was saved. Type exit to return.')
            return shell(environ)
        if choice == 'no':
            say('No session opened. Save the two named Codespaces secrets and restart, then run make doctor.')
            return 0
        say('No session opened. Run make telegram again and answer yes or no, or save the named secrets and restart.')
        return 1
    except (KeyboardInterrupt, EOFError):
        say('Setup stopped. No assistant was started; run make telegram when you are ready.')
    except BlockingIOError:
        say('A local process is using this shop. Stop its foreground command with Ctrl-C before make telegram.')
    except Exception as error:
        say(problem_hint(error))
    return 1


def sheet_status(environ):
    """Probe in the separate server runtime; suppress all provider output."""
    project = Path(__file__).resolve().parent.parent
    python = project / 'server' / '.venv' / 'bin' / 'python'
    if not python.is_file():
        return 'environment missing; run make setup'
    try:
        process = subprocess.run([str(python), '-B', '-m', 'shop_demo.status_sheet'],
            env=environ, cwd=project, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
        return 'reachable (metadata read only)' if process.returncode == 0 else 'not reachable; run make google-signin and check SHOP_SHEET_ID'
    except Exception:
        return 'check did not finish; check the network and run make status again'


def status(environ=None, *, request=api, probe=sheet_status, activity=local_activity, output=None):
    environ = dict(os.environ if environ is None else environ)
    output = sys.stdout if output is None else output
    ok = True
    def say(text):
        print(text, file=output, flush=True)
    say('Checking local assistant, Telegram identity and read-only Sheet access...')
    token, chat = environ.get('TELEGRAM_BOT_TOKEN', ''), environ.get('SHOP_OPERATOR_CHAT_ID', '')
    try:
        token = Token(value=SecretStr(token)).checked()
        identity = BotIdentity.model_validate(request(token, 'getMe', {}))
        say(f'Telegram bot: @{identity.username}.')
        webhook = Webhook.model_validate(request(token, 'getWebhookInfo', {}))
        if webhook.url.get_secret_value():
            say('Telegram delivery: webhook configured; use a separate personal bot for this polling example.')
            ok = False
        else:
            say('Telegram delivery: no webhook. Status does not poll messages or rule out a remote reader.')
    except Exception as error:
        say(problem_hint(error))
        ok = False
    valid_chat = bool(re.fullmatch(r'[1-9][0-9]*', chat))
    say('Private chat: SHOP_OPERATOR_CHAT_ID ' + ('configured; discovery is checked by make telegram.' if valid_chat else 'missing or invalid; run make telegram.'))
    if not valid_chat:
        ok = False
    try:
        state = activity(environ.get('SHOP_STATE_DIR', '.state'), token, chat)
        lines = {'running': 'Local assistant: running for these Telegram settings.',
            'stopped': 'Local assistant: stopped. Run make run when make doctor passes.',
            'different': 'Local process: active with different Telegram settings. Return to its terminal before changing settings.',
            'unknown': 'Local process: active; its owner is unknown. Check its foreground terminal before starting another assistant.'}
        say(lines[state])
        if state in {'different', 'unknown'}:
            ok = False
    except Exception:
        say('Local activity: unavailable. Preserve .state and check its private file permissions before restarting.')
        ok = False
    if not environ.get('GOOGLE_TOKEN_JSON', '').strip() or not re.fullmatch(r'[A-Za-z0-9_-]{20,120}', environ.get('SHOP_SHEET_ID', '')):
        say('Sheet: settings missing or invalid. Set SHOP_SHEET_ID and run make google-signin; make doctor explains all names.')
        ok = False
    else:
        try:
            result = probe(environ)
        except Exception:
            result = 'check did not finish; check the network and run make status again'
        say('Sheet: ' + result + '.')
        if result != 'reachable (metadata read only)':
            ok = False
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['telegram', 'status'])
    command = parser.parse_args().command
    return guided() if command == 'telegram' else status()


if __name__ == '__main__':
    raise SystemExit(main())
