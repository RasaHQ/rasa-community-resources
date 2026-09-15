#!/usr/bin/env python3
"""DevPilot MCP demo server.

A real Model Context Protocol (MCP) server exposed over HTTP using the
installed `mcp` SDK (FastMCP). It exposes a couple of remote tools that the
DevPilot agent would otherwise have as local Python functions.

Run it standalone:
    uv run python scripts/mcp_demo_server.py

Then the client can list + call the tools over Streamable HTTP.
"""

from __future__ import annotations

import time

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("devpilot-mcp-demo")


@mcp.tool()
def get_system_time(timezone: str = "UTC") -> dict:
    """Return the current local time. Big picture: a remote utility tool.

    Args:
        timezone: IANA timezone name (ignored in the demo, always UTC).
    """
    return {
        "timezone": timezone,
        "epoch": int(time.time()),
        "human": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


@mcp.tool()
def check_license_seats(product: str) -> dict:
    """Check how many seats are left on a developer tool license.

    Args:
        product: Product name, e.g. github-copilot, jetbrains-ultimate,
            figma, or sentry.
    """
    catalog = {
        "github-copilot": {"total": 20, "used": 18},
        "jetbrains-ultimate": {"total": 8, "used": 8},
        "figma": {"total": 15, "used": 11},
        "sentry": {"total": 10, "used": 3},
    }
    row = catalog.get(product.lower())
    if not row:
        return {"product": product, "found": False}
    remaining = row["total"] - row["used"]
    return {
        "product": product,
        "found": True,
        "total_seats": row["total"],
        "used_seats": row["used"],
        "seats_left": remaining,
        "exhausted": remaining == 0,
    }


if __name__ == "__main__":
    # Serve over Streamable HTTP. Defaults to http://localhost:8000/mcp
    print("DevPilot MCP demo server starting on http://localhost:8000/mcp ...")
    mcp.run(transport="streamable-http")
