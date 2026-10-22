"""One authenticated Mantle task tool over MCP streamable HTTP.

Targets mcp 1.26.0. App construction does not start a service or read secrets.
The facilitator launcher supplies a runtime-only transport token. Neither
OpenAI nor provider credentials belong in MCP metadata or tool arguments.
"""
from contextlib import asynccontextmanager
import secrets
import json
from typing import Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.tools.base import Tool
from pydantic import BaseModel, ConfigDict

from briefing.jobs import Jobs
from briefing.board_display import BoardDisplay
from project.lib.capability_logging import contains_api_key, redact_api


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
        self._display = None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/cards" and self._display is not None:
            return await self._display(scope, receive, send)
        if scope["type"] != "http":
            return await self._app(scope, receive, send)
        headers = [value for name, value in scope.get("headers", []) if name.lower() == b"authorization"]
        expected = ("Bearer " + self._token).encode()
        if len(headers) != 1 or not secrets.compare_digest(headers[0], expected):
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b'{"error":"unauthenticated_peer"}'})
            return
        # Inspect the bounded complete request BEFORE FastMCP/Pydantic can
        # log or shorten validation inputs. Decode JSON escape sequences here.
        request_body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            request_body.extend(message.get('body', b''))
            if len(request_body) > 4 * 1024 * 1024:
                await send({'type': 'http.response.start', 'status': 413,
                            'headers': [(b'content-type', b'application/json')]})
                await send({'type': 'http.response.body', 'body': b'{"error":"request_limit"}'})
                return
            if not message.get('more_body', False):
                break
        try:
            decoded = json.loads(request_body)
        except (ValueError, UnicodeDecodeError):
            decoded = None
        if contains_api_key(decoded) or contains_api_key(request_body.decode('utf-8', errors='replace')):
            rpc_id = decoded.get('id') if isinstance(decoded, dict) else None
            if not isinstance(rpc_id, (str, int)) or contains_api_key(rpc_id):
                rpc_id = None
            body = json.dumps({'jsonrpc': '2.0', 'id': rpc_id,
                               'error': {'code': -32602, 'message': 'api_credentials_forbidden_in_mcp'}}).encode()
            await send({'type': 'http.response.start', 'status': 200,
                        'headers': [(b'content-type', b'application/json')]})
            await send({'type': 'http.response.body', 'body': body})
            return
        delivered = False

        async def inspected_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(request_body), 'more_body': False}
            return await receive()

        # Request scope is created by the server, never copied from model data.
        scope = {**scope, "briefing.peer": "mantle"}
        # Protect even SDK validation errors produced before the tool function,
        # including echoed extra arguments or JSON-RPC metadata. Stateless JSON
        # responses are buffered to avoid split-chunk credential leakage.
        start = None
        chunks = bytearray()

        async def safe_send(message):
            nonlocal start
            if message['type'] == 'http.response.start':
                start = message
            elif message['type'] == 'http.response.body':
                chunks.extend(message.get('body', b''))
                if len(chunks) > 4 * 1024 * 1024:
                    raise ValueError('public_response_limit')
                if not message.get('more_body', False):
                    body = redact_api(chunks.decode('utf-8')).encode('utf-8')
                    headers = [(k, v) for k, v in start.get('headers', [])
                               if k.lower() != b'content-length']
                    await send({**start, 'headers': headers + [(b'content-length', str(len(body)).encode())]})
                    await send({'type': 'http.response.body', 'body': body})
            else:
                await send(message)

        return await self._app(scope, inspected_receive, safe_send)


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
        if contains_api_key(metadata) or contains_api_key((request, briefing_id, change)):
            raise ValueError('api_credentials_forbidden_in_mcp')
        result = await jobs.from_transport(peer, metadata, action=action, request=request,
                                           job_id=briefing_id, change=change)
        if "job_id" in result:
            result["briefing_id"] = result.pop("job_id")
        result["binding"] = "capability_id" if jobs.ownership_mode == "capability" else "engine_sender"
        # Credentials never belong in cards, errors, questions or MCP results.
        # Preserve the briefing capability: get/revise need that private ID.
        clean = redact_api({k: v for k, v in result.items() if k != 'briefing_id'})
        if 'briefing_id' in result:
            clean['briefing_id'] = result['briefing_id']
        return BriefingResponse.model_validate(clean)

    tool = Tool.from_function(briefing, description="Start, inspect or revise a briefing using its unguessable briefing_id capability. Possession permits access; this mode is not engine-sender binding. Never supply user or session identity.")

    class StrictArguments(tool.fn_metadata.arg_model):
        # FastMCP's generated default silently discards extra keys. This public
        # contract refuses them, including obsolete job_id and invented owner.
        model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    tool.fn_metadata.arg_model = StrictArguments
    tool.parameters = StrictArguments.model_json_schema(by_alias=True)
    server = FastMCP("briefing", tools=[tool], host="127.0.0.1", port=8942,
                     stateless_http=True, json_response=True, lifespan=lifespan)
    def render_current_board():
        # One renderer, owned by Core. No local HTML/card implementation.
        from zeo_core.adapters.widget_html import render_snapshot_html
        return render_snapshot_html(jobs.display_snapshot(), document=True, title=jobs.display_title())

    peer = _MantlePeer(server.streamable_http_app(), transport_token)
    peer._display = BoardDisplay(peer._app, render_current=render_current_board)
    return peer
