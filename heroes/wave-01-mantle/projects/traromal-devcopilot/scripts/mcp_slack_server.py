#!/usr/bin/env python3
"""DevPilot MCP bridge for Slack.

Exposes a few Slack Web API operations as MCP tools so the DevPilot agent can
post dev updates to a workspace channel. Uses httpx directly against the Slack
Web API (no slack_sdk dependency).

Requires SLACK_BOT_TOKEN in the environment (or .env).

Run it standalone:
    uv run python scripts/mcp_slack_server.py
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SLACK_API = "https://slack.com/api"

mcp = FastMCP("devpilot-mcp-slack")


def _headers() -> dict:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@mcp.tool()
def post_message(channel: str, text: str) -> dict:
    """Post a message to a Slack channel.

    Args:
        channel: Channel name (with or without leading #) or channel ID,
            e.g. "general" or "dev-updates".
        text: The message text to post.
    """
    body = {"channel": channel.lstrip("#") if not channel.startswith(("C", "G")) else channel, "text": text}
    with httpx.Client(timeout=15) as client:
        resp = client.post(f"{SLACK_API}/chat.postMessage", json=body, headers=_headers())
        data = resp.json()
    return {"ok": data.get("ok", False), "error": data.get("error"), "channel": channel, "ts": data.get("ts")}


@mcp.tool()
def list_messages(channel: str, limit: int = 20) -> dict:
    """Read recent messages from a public channel."""
    channel_id = channel.lstrip("#")
    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{SLACK_API}/conversations.history", params={"channel": channel_id, "limit": max(1, min(int(limit), 100))}, headers=_headers())
        data = resp.json()
    return {"ok": data.get("ok", False), "error": data.get("error"), "channel": channel, "messages": [
        {"user": m.get("user"), "text": m.get("text"), "ts": m.get("ts"), "thread_ts": m.get("thread_ts")}
        for m in data.get("messages", [])
    ]}


@mcp.tool()
def reply_in_thread(channel: str, thread_ts: str, text: str) -> dict:
    """Post a reply to an existing Slack thread."""
    channel_id = channel.lstrip("#")
    body = {"channel": channel_id, "text": text, "thread_ts": thread_ts}
    with httpx.Client(timeout=15) as client:
        resp = client.post(f"{SLACK_API}/chat.postMessage", json=body, headers=_headers())
        data = resp.json()
    return {"ok": data.get("ok", False), "error": data.get("error"), "channel": channel, "thread_ts": thread_ts, "ts": data.get("ts")}


@mcp.tool()
def add_reaction(channel: str, timestamp: str, emoji: str) -> dict:
    """Add an emoji reaction to a Slack message."""
    channel_id = channel.lstrip("#")
    body = {"channel": channel_id, "timestamp": timestamp, "name": emoji.lstrip(":").rstrip(":")}
    with httpx.Client(timeout=15) as client:
        resp = client.post(f"{SLACK_API}/reactions.add", json=body, headers=_headers())
        data = resp.json()
    return {"ok": data.get("ok", False), "error": data.get("error"), "channel": channel, "timestamp": timestamp, "emoji": emoji}


@mcp.tool()
def list_channels() -> dict:
    """List public channels in the workspace the bot has access to.

    Returns:
        A dict with a channel list, each with id and name.
    """
    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{SLACK_API}/conversations.list", params={"types": "public_channel", "limit": 100}, headers=_headers())
        data = resp.json()
    return {
        "ok": data.get("ok", False),
        "error": data.get("error"),
        "channels": [{"id": c.get("id"), "name": c.get("name")} for c in data.get("channels", [])],
    }


if __name__ == "__main__":
    print("DevPilot MCP Slack server starting on http://localhost:8001/mcp ...")
    print("(Use scripts/mcp_slack_serve.py instead - direct run binds :8000.)")
    mcp.run(transport="streamable-http")
