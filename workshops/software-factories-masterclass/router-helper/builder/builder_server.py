"""A small tool server that puts your builder behind the router helper.

Mantle (and, in files, a Rasa flow) can call this server's one tool, build_change. The tool runs one builder
session (builder.py) and returns what the builder said and whether it saved a file. It listens on 127.0.0.1 only.

Run it:  python3 builder_server.py        (needs: pip install --upgrade openai mcp==1.28.1)
The same FastMCP setup is used by examples/mantle-factory-agent/server.py in this repository.

Not run yet by anyone for this workshop.
"""
import asyncio
import os
import sys

from mcp.server.fastmcp import FastMCP

import builder

PORT = int(os.environ.get("BUILDER_MCP_PORT", "8765"))

server = FastMCP("builder", host="127.0.0.1", port=PORT, stateless_http=True, json_response=True)
busy = asyncio.Lock()


@server.tool()
async def build_change(request: str) -> dict:
    """Ask the builder agent to build one small change to the router helper. Describe the change in one sentence.
    Returns whether a file was saved and what the builder said. Nothing is applied to the helper."""
    if busy.locked():
        return {"saved": False, "builder_said": "A build is already running. Wait for it to finish."}
    async with busy:
        outcome = await asyncio.to_thread(builder.build, request, False)
    return {"saved": outcome["saved"], "builder_said": outcome["builder_said"][:2000]}


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set the OPENAI_API_KEY Codespaces secret for this repository, then restart the codespace.")
    server.run(transport="streamable-http")
