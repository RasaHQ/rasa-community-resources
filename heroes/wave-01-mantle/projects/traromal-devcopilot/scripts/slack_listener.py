#!/usr/bin/env python3
"""Bidirectional Slack listener for DevPilot.

Connects to Slack via Socket Mode (outbound websocket - no public URL
needed), listens in channels the bot is in, forwards each message to the
DevPilot REST API (:5006), and posts DevPilot's reply back to Slack.

Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env (dotenv is auto-loaded).

Run:
    uv run python scripts/slack_listener.py
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk import WebClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RASA_URL = os.environ.get("RASA_URL", "http://localhost:5006")
CHANNEL_INCLUDE = [c.strip().lstrip("#") for c in os.environ.get("SLACK_CHANNELS", "all-devcopilot").split(",") if c.strip()]


def _rasa_chat(user_id: str, text: str) -> str:
    """Send a user message to DevPilot and return the aggregated reply text."""
    sender = f"slack-{user_id}"
    payload = {"sender": sender, "message": text}
    with httpx.Client(timeout=120) as client:
        resp = client.post(f"{RASA_URL}/webhooks/rest/webhook", json=payload)
        resp.raise_for_status()
        messages = resp.json()
    return "\n".join(m.get("text", "") for m in messages if m.get("text"))


client = SocketModeClient(
    app_token=os.environ["SLACK_APP_TOKEN"],
    web_client=WebClient(token=os.environ["SLACK_BOT_TOKEN"]),
)


def _resolve_channel_ids(names: list[str]) -> set[str]:
    """Map channel names to channel IDs so the message filter works."""
    if not names:
        return set()
    try:
        resp = client.web_client.conversations_list(types="public_channel", limit=200)
        by_name = {c.get("name"): c.get("id") for c in resp.get("channels", [])}
    except Exception:  # noqa: BLE001 - fall back to matching raw IDs
        return set()
    ids = {by_name.get(n) for n in names}
    ids.update(names)
    return {i for i in ids if i}


CHANNEL_IDS = _resolve_channel_ids(CHANNEL_INCLUDE)
BOT_USER_ID = os.environ.get("SLACK_BOT_USER_ID", "U0C1BCCJR99")


def handle(client_inner: SocketModeClient, request: SocketModeRequest) -> None:
    if request.type != "events_api":
        return
    client_inner.send_socket_mode_response(SocketModeResponse(envelope_id=request.envelope_id))
    event = request.payload.get("event", {})
    etype = event.get("type", "")
    print(f"[debug] event type={etype} channel={event.get('channel')} user={event.get('user')}", flush=True)
    if etype not in ("message", "app_mention"):
        return
    if "subtype" in event:
        return
    channel = event.get("channel", "")
    if CHANNEL_IDS and channel not in CHANNEL_IDS:
        print(f"[debug] ignored channel {channel}", flush=True)
        return
    text = event.get("text", "")
    user = event.get("user", "")
    if not text or not user:
        return
    if user == BOT_USER_ID:
        return
    if f"<@{BOT_USER_ID}>" not in text and not text.strip().lower().startswith("hey devpilot"):
        print("[debug] no mention, ignoring", flush=True)
        return
    print(f"[debug] forwarding: {text}", flush=True)
    try:
        reply = _rasa_chat(user, text)
    except Exception as exc:  # noqa: BLE001 - surface errors to the caller in Slack
        reply = f"Sorry - I hit an error talking to DevPilot: {exc}"
    if reply:
        print(f"[debug] posting reply ...", flush=True)
        client_inner.web_client.chat_postMessage(channel=channel, text=reply, thread_ts=event.get("ts"))


client.socket_mode_request_listeners.append(handle)
if __name__ == "__main__":
    print(f"DevPilot Slack listener on channels {CHANNEL_INCLUDE} - waiting for @DevPilot mentions...", flush=True)
    client.connect()
    while True:
        import time

        time.sleep(1)