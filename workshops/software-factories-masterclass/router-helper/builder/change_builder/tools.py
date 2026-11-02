"""The change builder's one tool: ask the builder tool server for a build, then show the customer what came back.

Mantle sends the customer a message from inside a tool with `context.send`, so the build id, the saved flag, the file path
and the sha256 reach the customer exactly as the builder server returned them, not as the model words them.
The builder server must be running (builder_server.py, 127.0.0.1:8765).
"""
import json
import os
import re
from datetime import timedelta

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

URL = os.environ.get("BUILDER_MCP_URL", "http://127.0.0.1:8765/mcp")
WAIT_SECONDS = 360


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def describe(result: dict) -> str:
    """The message the customer sees. Built only from fields the builder server returned, and only if they are well formed.

    "No build started" is said only when the server itself says so (started is False, the busy refusal). A result that
    is incomplete or malformed is unknown: the request may have reached the builder.
    """
    unknown = ("I cannot tell whether a build started or what it produced. "
               "I did not try again. Check the tool server's terminal before asking for another build.")
    if not isinstance(result, dict):
        return unknown
    said = str(result.get("builder_said", ""))[:300]
    if result.get("started") is False:
        return "No build started. " + said
    build_id, saved = result.get("build_id"), result.get("saved")
    if not _text(build_id) or not isinstance(saved, bool):
        return unknown
    if saved:
        path, digest = result.get("file"), result.get("sha256")
        if not (_text(path) and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)):
            return f"Build {build_id} reported a saved file, but its path or sha256 is missing or malformed. Do not use it."
        return f"Build {build_id} saved a file. Path: {path}. sha256: {digest}. Nothing was applied to the helper."
    return (f"Build {build_id} reported no saved file (saved=false). {said} "
            "I cannot confirm that the build has ended. Nothing was applied to the helper.")


def parse(call_result) -> dict:
    """The server's dict, from structured content when present, else from the first text block.

    An error result, or one that is not a dict, parses to {} so describe() says it cannot tell. Malformed text raises,
    and the caller treats that the same way.
    """
    if getattr(call_result, "isError", False):
        return {}
    structured = getattr(call_result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured.get("result", structured) if set(structured) == {"result"} else structured
    for block in getattr(call_result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
    return {}


async def _call_server(request: str):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(URL, timeout=30, sse_read_timeout=WAIT_SECONDS + 30) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool("build_change", {"request": request},
                                           read_timeout_seconds=timedelta(seconds=WAIT_SECONDS))


@tool(description="Ask the builder for one small change to the router helper. Shows the customer the build id, saved flag, file path and sha256.")
async def build_change(request: str, context: ToolContext = None) -> ToolResult:
    try:
        result = parse(await _call_server(request))
    except Exception as error:  # a timeout or a bad answer does not prove that no build started
        result = {"builder_said": f"The builder did not give a usable answer ({type(error).__name__})."}
    message = describe(result)
    await context.send(message)
    return ToolResult(llm_response={"shown_to_customer": message})
