# SPDX-License-Identifier: MIT
"""A naked MCP server for the Fiserv Banking Hub release teaching example.

It lives inside this example and imports nothing from another example. It
exposes exactly seven read-only tools; facts the release cannot supply answer
"unavailable" with a closed reason. Identity, assurance and reset are private
host calls on a separate capability-protected path; they are not MCP tools.
No path sends a transfer.
"""
from __future__ import annotations

from hmac import compare_digest
import json
import os
from secrets import token_urlsafe
import sys
from threading import RLock

from mcp.server.fastmcp import Context, FastMCP
from starlette.responses import JSONResponse

from .host import BankingHubService, Refused

TOOLS = {
    "banking_accounts": {},
    "banking_balance": {"account": "string"},
    "banking_history": {"account": "string", "page": "integer?"},
    "banking_loan_payment": {"account": "string"},
    "banking_payoff": {"account": "string"},
    "banking_review_transfer": {"source": "string", "destination": "string",
                                "amount": "string", "currency": "string"},
    "banking_transfer_status": {},
}


def _input_schema(spec: dict) -> dict:
    properties, required = {}, []
    for name, kind in spec.items():
        optional = kind.endswith("?")
        properties[name] = {"type": kind.rstrip("?")}
        if not optional:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


def check_arguments(tool: str, arguments) -> None:
    """Raw validation before SDK coercion so no extra field can slip through."""
    spec = TOOLS[tool]
    if not isinstance(arguments, dict) or set(arguments) - set(spec):
        raise ValueError("arguments")
    for name, kind in spec.items():
        if name not in arguments:
            if not kind.endswith("?"):
                raise ValueError("missing")
            continue
        wanted = kind.rstrip("?")
        value = arguments[name]
        if wanted == "string" and not (isinstance(value, str) and len(value) <= 64):
            raise ValueError("type")
        if wanted == "integer" and type(value) is not int:
            raise ValueError("type")


class _Server(FastMCP):
    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.inputSchema = _input_schema(TOOLS[tool.name])
        return tools


class _Registry:
    def __init__(self, host_token, service):
        self.host_token, self.service = host_token, service
        self.sessions, self.lock = {}, RLock()

    def context(self, token):
        with self.lock:
            context = self.sessions.get(token)
        if context is None:
            raise Refused("invalid_host_binding")
        return context

    def open(self, caller):
        context = self.service.open_session(caller)
        token = token_urlsafe(32)
        with self.lock:
            self.sessions[token] = context
        return token


class _Capabilities:
    def __init__(self, app, registry):
        self.app, self.registry = app, registry

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"")
        token = authorization[7:].decode("ascii", "ignore") if authorization.startswith(b"Bearer ") else ""
        if scope["path"].startswith("/host/"):
            allowed = compare_digest(token, self.registry.host_token)
        else:
            try:
                scope["bankinghub_context"] = self.registry.context(token)
                allowed = True
            except Refused:
                allowed = False
        if not allowed:
            return await JSONResponse({"state": "refused"}, status_code=401)(scope, receive, send)
        if scope["path"].startswith("/mcp/"):
            return await JSONResponse({"state": "refused"}, status_code=404)(scope, receive, send)
        if scope["path"] == "/mcp" and scope["method"] == "POST":
            captured = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                captured.extend(message.get("body", b""))
                if len(captured) > 65536:
                    return await JSONResponse({"state": "refused"}, status_code=413)(scope, receive, send)
                if not message.get("more_body", False):
                    break
            try:
                payload = json.loads(captured)
            except (ValueError, UnicodeError):
                payload = None
            if not isinstance(payload, dict):
                return await JSONResponse({"jsonrpc": "2.0", "id": None, "error": {
                    "code": -32600, "message": "invalid_banking_request"}}, status_code=400)(scope, receive, send)
            if payload.get("method") == "tools/call":
                try:
                    params = payload["params"]
                    if params["name"] not in TOOLS:
                        raise ValueError()
                    check_arguments(params["name"], params.get("arguments", {}))
                except Exception:
                    return await JSONResponse({"jsonrpc": "2.0", "id": payload.get("id"), "error": {
                        "code": -32602, "message": "invalid_banking_arguments"}})(scope, receive, send)
            sent, upstream = False, receive

            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": bytes(captured), "more_body": False}
                return await upstream()

            receive = replay
        return await self.app(scope, receive, send)


def create_app(service: BankingHubService, host_token: str):
    if not isinstance(host_token, str) or len(host_token) < 32 or not host_token.isascii():
        raise ValueError("host capability must be at least 32 ASCII characters")
    registry = _Registry(host_token, service)
    server = _Server("fiserv-banking-hub-release", host="127.0.0.1", stateless_http=True, json_response=True)

    def invoke(ctx, method, *args):
        context = ctx.request_context.request.scope["bankinghub_context"]
        try:
            return method(context, *args)
        except Refused as exc:
            return {"state": "refused", "reason": str(exc)}

    @server.tool(structured_output=True)
    def banking_accounts(ctx: Context) -> dict[str, object]:
        """List the caller's permitted fictional account aliases."""
        return invoke(ctx, service.accounts)

    @server.tool(structured_output=True)
    def banking_balance(account: str, ctx: Context) -> dict[str, object]:
        """Available balance of one permitted DDA or SDA alias (not in this release)."""
        return invoke(ctx, service.balance, account)

    @server.tool(structured_output=True)
    def banking_history(account: str, ctx: Context, page: int = 1) -> dict[str, object]:
        """Posted transactions of one permitted alias (not in this release)."""
        return invoke(ctx, service.history, account, page)

    @server.tool(structured_output=True)
    def banking_loan_payment(account: str, ctx: Context) -> dict[str, object]:
        """Next payment date of one permitted LOAN alias; the amount is not in this release."""
        return invoke(ctx, service.loan_payment, account)

    @server.tool(structured_output=True)
    def banking_payoff(account: str, ctx: Context) -> dict[str, object]:
        """Payoff of one permitted LOAN alias (not in this release)."""
        return invoke(ctx, service.payoff, account)

    @server.tool(structured_output=True)
    def banking_review_transfer(source: str, destination: str, amount: str, currency: str,
                                ctx: Context) -> dict[str, object]:
        """Transfers are not available in this release example. Never sends anything."""
        return invoke(ctx, service.review_transfer, source, destination, amount, currency)

    @server.tool(structured_output=True)
    def banking_transfer_status(ctx: Context) -> dict[str, object]:
        """Transfer outcome: none can exist in this release example."""
        return invoke(ctx, service.status)

    app = server.streamable_http_app()

    async def host_control(request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise Refused("invalid_host_request")
            path = request.url.path
            if path == "/host/open":
                return JSONResponse({"credential": registry.open(body.get("caller")),
                                     "identity": "simulated-only"})
            token = body.get("credential")
            context = registry.context(token) if isinstance(token, str) else None
            if context is None:
                raise Refused("invalid_host_binding")
            if path == "/host/assure":
                service.assure(context, body.get("age"))
                return JSONResponse({"state": "assured"})
            if path == "/host/confirm":
                service.confirm(context, body.get("review"), body.get("transfer"))
                return JSONResponse({"state": "confirmed"})
            if path == "/host/cancel":
                return JSONResponse(service.cancel(context, body.get("review")))
            if path == "/host/submit":
                return JSONResponse(service.submit(context, body.get("review")))
            if path == "/host/reset":
                service.reset(context)
                with registry.lock:
                    registry.sessions.pop(token, None)
                return JSONResponse({"state": "reset"})
        except Refused as exc:
            return JSONResponse({"state": "refused", "reason": str(exc)}, status_code=403)
        except Exception:
            return JSONResponse({"state": "refused", "reason": "invalid_host_request"}, status_code=400)
        return JSONResponse({"state": "refused"}, status_code=404)

    for route in ("open", "assure", "confirm", "cancel", "submit", "reset"):
        app.add_route("/host/" + route, host_control, methods=["POST"])
    app.add_middleware(_Capabilities, registry=registry)
    return app


def serve_backend():
    """Private child entrypoint: consume the already-bound loopback descriptors.

    argv: mock_fd mcp_fd. The vendor definitions are read here, at run time,
    from the learner-supplied archive; a missing or changed file stops the
    backend with a short message.
    """
    import socket
    import uvicorn
    from .client import BankingHubClient
    from .contract import ContractError, BankingHubContract
    from .mock import MOCK_ORGANIZATION, BankingHubMock, serve
    mock_fd, mcp_fd = sys.argv[1], sys.argv[2]
    try:
        contract = BankingHubContract.from_path()
    except ContractError as exc:
        print(str(exc), flush=True)
        raise SystemExit(3)
    mock_socket = socket.socket(fileno=int(mock_fd))
    serve(BankingHubMock(contract), mock_socket)
    port = mock_socket.getsockname()[1]
    client = BankingHubClient(contract, f"http://127.0.0.1:{port}", MOCK_ORGANIZATION)
    from .permissions import PERMISSIONS
    service = BankingHubService(client, PERMISSIONS)
    app = create_app(service, os.environ.get("BANKINGHUB_HOST_CAPABILITY", ""))
    uvicorn.run(app, fd=int(mcp_fd), access_log=False, log_level="warning")


if __name__ == "__main__":
    serve_backend()
