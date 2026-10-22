"""One authenticated Mantle task tool over MCP streamable HTTP.

Targets mcp 1.26.0. App construction does not start a service or read secrets.
The facilitator launcher supplies a runtime-only transport token. Neither
OpenAI nor provider credentials belong in MCP metadata or tool arguments.
"""
from contextlib import asynccontextmanager
import secrets
import json
from typing import Literal, Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.tools.base import Tool
from pydantic import BaseModel, ConfigDict, Field

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
    discovery_id: str | None = None
    candidates: list[dict] | None = None
    source_date: str | None = None
    label: str | None = None
    coverage: str | None = None
    message: str | None = None
    partial: bool | None = None


class _MantlePeer:
    """Only verified transport calls may assert a conversation via _meta."""

    def __init__(self, app, token: str):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("runtime_transport_token_required")
        self._app, self._token = app, token
        self._display = None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") in ("/", "/cards") and self._display is not None:
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


def create_app(jobs: Jobs, *, transport_token: str, host="127.0.0.1"):
    from demo_host import validate_host, display_hosts
    from mcp.server.transport_security import TransportSecuritySettings
    validate_host(host)
    async def dispatch(ctx: Context, **arguments) -> BriefingResponse:
        context = ctx.request_context
        incoming = context.request
        peer = incoming.scope.get("briefing.peer") if incoming is not None else None
        metadata = context.meta.model_dump(by_alias=True) if context.meta is not None else None
        if contains_api_key(metadata) or contains_api_key(arguments):
            raise ValueError('api_credentials_forbidden_in_mcp')
        result = await jobs.from_transport(peer, metadata, **arguments)
        if "job_id" in result:
            result["briefing_id"] = result.pop("job_id")
        result["binding"] = "capability_id" if jobs.ownership_mode == "capability" else "engine_sender"
        # Credentials never belong in cards, errors, questions or MCP results.
        # Preserve the briefing capability: get/revise need that private ID.
        clean = redact_api({k: v for k, v in result.items() if k != 'briefing_id'})
        if 'briefing_id' in result:
            clean['briefing_id'] = result['briefing_id']
        return BriefingResponse.model_validate(clean)

    async def briefing(action: Literal["start", "get", "revise"], ctx: Context,
                       request: str | None = None, briefing_id: str | None = None,
                       change: str | None = None, discovery_id: str | None = None,
                       choice: Annotated[int, Field(ge=1, le=5)] | None = None) -> BriefingResponse:
        return await dispatch(ctx, action=action, request=request, job_id=briefing_id,
                              change=change, discovery_id=discovery_id, choice=choice)

    async def find_flights(destination: Annotated[str, Field(min_length=1, max_length=120)],
                           ctx: Context) -> BriefingResponse:
        return await dispatch(ctx, action='find_flights', request=destination)

    def strict_tool(function, description):
        tool = Tool.from_function(function, description=description)
        class StrictArguments(tool.fn_metadata.arg_model):
            model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)
        tool.fn_metadata.arg_model = StrictArguments
        tool.parameters = StrictArguments.model_json_schema(by_alias=True)
        return tool

    tools = [strict_tool(briefing, "Start, inspect or revise a traveller briefing. Pass the traveller's exact words in request/change. To select a discovered flight, pass its private discovery_id and numbered choice; never invent a flight or supply user/session identity. Keep capability identifiers private."),
             strict_tool(find_flights, "Find up to five flights already in the air approaching New York or its named airport, using observed positions and dated published routes. Pass the traveller's destination in ordinary words. Return the reader's choices; never invent candidates or landing estimates. Keep the discovery_id private.")]
    server = FastMCP("briefing", tools=tools, host=host, port=8942,
                     transport_security=TransportSecuritySettings(
                         enable_dns_rebinding_protection=True,
                         allowed_hosts=[value + ":*" for value in display_hosts(host)],
                         allowed_origins=["http://" + value + ":*" for value in display_hosts(host)]),
                     stateless_http=True, json_response=True)
    def render_current_board():
        # One renderer, owned by Core. No local HTML/card implementation.
        from zeo_core.adapters.widget_html import render_snapshot_html
        snapshot = jobs.display_snapshot()
        if not snapshot:
            from briefing.board_display import start_panel
            return start_panel(jobs.display_status(), discovery=jobs.display_discovery())
        from briefing.board_display import brand_document
        return brand_document(render_snapshot_html(snapshot, document=True, title=jobs.display_title()))

    app = server.streamable_http_app()
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def application_lifespan(application):
        # FastMCP's protocol lifespan runs for stateless requests. A request
        # finishing must not cancel background jobs or erase the visible board.
        # The ASGI application's shutdown owns all job cleanup instead.
        try:
            async with original_lifespan(application) as state:
                yield state
        finally:
            await jobs.close()

    app.router.lifespan_context = application_lifespan
    peer = _MantlePeer(app, transport_token)
    peer._display = BoardDisplay(peer._app, render_current=render_current_board, host=host)
    return peer
