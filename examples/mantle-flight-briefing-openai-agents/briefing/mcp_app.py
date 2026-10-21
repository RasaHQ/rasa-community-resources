"""One authenticated Mantle task tool over MCP streamable HTTP.

Targets mcp 1.26.0. App construction does not start a service or read secrets.
The facilitator launcher supplies a runtime-only transport token. Neither
OpenAI nor provider credentials belong in MCP metadata or tool arguments.
"""
from contextlib import asynccontextmanager
import secrets
from typing import Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.tools.base import Tool
from pydantic import BaseModel, ConfigDict

from briefing.jobs import Jobs


class BriefingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    binding: str
    briefing_id: str | None = None
    revision: int | None = None
    request_id: str | None = None
    progress: list[str] | None = None
    widgets: list[str] | None = None
    cards: list[dict] | None = None
    reason: str | None = None
    needs_input: dict | None = None


class _MantlePeer:
    """Only verified transport calls may assert a conversation via _meta."""

    def __init__(self, app, token: str):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("runtime_transport_token_required")
        self._app, self._token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self._app(scope, receive, send)
        headers = [value for name, value in scope.get("headers", []) if name.lower() == b"authorization"]
        expected = ("Bearer " + self._token).encode()
        if len(headers) != 1 or not secrets.compare_digest(headers[0], expected):
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b'{"error":"unauthenticated_peer"}'})
            return
        # Request scope is created by the server, never copied from model data.
        scope = {**scope, "briefing.peer": "mantle"}
        return await self._app(scope, receive, send)


def create_app(jobs: Jobs, *, transport_token: str):
    @asynccontextmanager
    async def lifespan(server):
        try:
            yield {}
        finally:
            await jobs.close()

    async def briefing(action: Literal["start", "get", "revise"], ctx: Context,
                       request: str | None = None, briefing_id: str | None = None,
                       change: str | None = None) -> BriefingResponse:
        context = ctx.request_context
        incoming = context.request
        peer = incoming.scope.get("briefing.peer") if incoming is not None else None
        metadata = context.meta.model_dump(by_alias=True) if context.meta is not None else None
        result = await jobs.from_transport(peer, metadata, action=action, request=request,
                                           job_id=briefing_id, change=change)
        if "job_id" in result:
            result["briefing_id"] = result.pop("job_id")
        result["binding"] = "capability_id" if jobs.ownership_mode == "capability" else "engine_sender"
        return BriefingResponse.model_validate(result)

    tool = Tool.from_function(briefing, description="Start, inspect or revise a briefing using its unguessable briefing_id capability. Possession permits access; this mode is not engine-sender binding. Never supply user or session identity.")

    class StrictArguments(tool.fn_metadata.arg_model):
        # FastMCP's generated default silently discards extra keys. This public
        # contract refuses them, including obsolete job_id and invented owner.
        model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    tool.fn_metadata.arg_model = StrictArguments
    tool.parameters = StrictArguments.model_json_schema(by_alias=True)
    server = FastMCP("briefing", tools=[tool], host="127.0.0.1", port=8942,
                     stateless_http=True, json_response=True, lifespan=lifespan)
    return _MantlePeer(server.streamable_http_app(), transport_token)
