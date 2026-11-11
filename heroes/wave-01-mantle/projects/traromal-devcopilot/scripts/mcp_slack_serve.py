#!/usr/bin/env python3
"""Serve the DevPilot MCP Slack server over Streamable HTTP on :8001.

Same rationale as mcp_demo_serve.py: FastMCP's built-in run() defaults to
uvicorn with websockets (port 8000, conflicts with the licenses server), so we
serve the Starlette app ourselves with websockets disabled.
"""

from __future__ import annotations

import uvicorn

from scripts.mcp_slack_server import mcp

app = mcp.streamable_http_app()


if __name__ == "__main__":
    print("DevPilot MCP Slack server on http://localhost:8001/mcp")
    uvicorn.run(app, host="127.0.0.1", port=8001, ws="none")