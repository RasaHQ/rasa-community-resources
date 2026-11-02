"""A small tool server that puts your builder behind the router helper.

Mantle (and a Rasa project run from files) can call this server's one tool, build_change. The tool runs one builder
session (builder.py) and returns the build id, whether it saved a file, the file's sha256, and what the builder said.
It listens on 127.0.0.1 only. The tool URL is http://127.0.0.1:8765/mcp.

One build at a time. The server keeps the build "running" until the worker thread has really finished, even if the
caller gives up and cancels its request. A second request while a build is running is refused. Each build writes
to its own folder. The builder stops waiting for new events after BUILDER_MAX_SECONDS, which is not a hard limit on the whole build.

Run it:  python3 builder_server.py        (needs: pip install --upgrade openai mcp==1.28.1)
The same FastMCP setup is used by examples/mantle-factory-agent/server.py in this repository.

Not run yet by anyone for this workshop on a real key. The cancel behavior was reproduced with a fake builder and no key.
"""
import asyncio
import os
import sys
import threading

from mcp.server.fastmcp import FastMCP

import builder

PORT = int(os.environ.get("BUILDER_MCP_PORT", "8765"))

server = FastMCP("builder", host="127.0.0.1", port=PORT, stateless_http=True, json_response=True)
_running = threading.Lock()


def _work(request: str) -> dict:
    """Runs on a worker thread. The lock is released only when this function has really finished."""
    try:
        outcome = builder.build(request, False)
        return {key: outcome[key] for key in ("build_id", "saved", "file", "sha256", "session_id") if key in outcome} | {
            "builder_said": outcome["builder_said"][:2000]}
    finally:
        _running.release()


@server.tool()
async def build_change(request: str) -> dict:
    """Ask the builder agent to build one small change to the router helper. Describe the change in one sentence.
    Returns the build id, whether a file was saved, its sha256, and what the builder said. Nothing is applied."""
    if not _running.acquire(blocking=False):
        return {"started": False, "saved": False, "builder_said": "A build is already running. Wait for it to finish."}
    try:
        future = asyncio.get_running_loop().run_in_executor(None, _work, request)
    except BaseException:
        _running.release()
        raise
    # shield: if the caller cancels this request, the worker thread keeps going and keeps the lock until it ends.
    return await asyncio.shield(future)


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set the OPENAI_API_KEY Codespaces secret for this repository, then restart the codespace.")
    server.run(transport="streamable-http")
