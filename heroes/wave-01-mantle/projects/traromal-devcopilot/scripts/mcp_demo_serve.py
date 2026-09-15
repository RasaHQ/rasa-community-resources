#!/usr/bin/env python3
"""Serve the DevPilot MCP demo server over Streamable HTTP.

FastMCP's built-in `mcp.run(transport="streamable-http")` pulls in uvicorn's
websocket support, which is broken by the pinned websockets==10.4 in this
env. Streamable HTTP is pure HTTP though, so we serve the Starlette app
ourselves with websockets disabled.
"""

from __future__ import annotations

import uvicorn

from scripts.mcp_demo_server import mcp

app = mcp.streamable_http_app()


if __name__ == "__main__":
    print("DevPilot MCP demo server on http://localhost:8000/mcp")
    uvicorn.run(app, host="127.0.0.1", port=8000, ws="none")
