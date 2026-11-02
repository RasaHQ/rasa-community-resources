"""The change builder's one tool: ask the builder tool server for a build, then show the customer what came back.

Mantle sends the customer a message from inside a tool with `context.send`, so the build id, the saved flag, the file path
and the sha256 reach the customer exactly as the builder server returned them, not as the model words them.
The builder server must be running (builder_server.py, 127.0.0.1:8765).
"""
import json
import os
from datetime import timedelta

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

URL = os.environ.get("BUILDER_MCP_URL", "http://127.0.0.1:8765/mcp")
WAIT_SECONDS = 360


def describe(result: dict) -> str:
    """The message the customer sees. Built only from fields the builder server returned.

    "No build started" is said only when the server itself says so (started is False, the busy refusal). Anything else
    without a build id is unknown: the request may have reached the builder.
    """
    build_id = result.get("build_id")
    said = str(result.get("builder_said", ""))[:300]
    if result.get("started") is False:
        return "No build started. " + said
    if not build_id:
        return ("I cannot tell whether a build started. " + (said + " " if said else "")
                + "I did not try again. Check the tool server's terminal before asking for another build.")
    if result.get("saved"):
        return (f"Build {build_id} saved a file. Path: {result.get('file', 'not reported')}. "
                f"sha256: {result.get('sha256', 'not reported')}. Nothing was applied to the helper.")
    return f"Build {build_id} ended without a saved file. {said} Nothing was applied to the helper."


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
