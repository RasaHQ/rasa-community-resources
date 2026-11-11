"""Loopback MCP domain simulator with a separate host capability interface.

This is not bank authentication or a vendor-wire mock. A trusted native channel
must still supply real user-turn provenance before calling the host interface.
"""

import argparse
from hmac import compare_digest
import os
from secrets import token_urlsafe
from threading import RLock
from time import monotonic
from uuid import uuid4

from mcp.server.fastmcp import Context, FastMCP
from starlette.responses import JSONResponse

from .contract import CONTRACT, public_result, schema, validate
from .mock import BankingMock
from .service import BankingService, Refused, SessionContext


class _BankingMCP(FastMCP):
    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.inputSchema = schema(tool.name, "input")
            tool.outputSchema = schema(tool.name, "output")
        return tools


class _Registry:
    def __init__(self, host_token, profile, fault):
        self.host_token = host_token
        self.bank = BankingService(BankingMock(profile, fault=fault))
        self.sessions = {}
        self.lock = RLock()

    def context(self, token):
        with self.lock:
            context = self.sessions.get(token)
        if context is None:
            raise Refused("invalid_host_binding")
        return context

    def open(self, caller):
        if caller not in {"demo-A", "demo-B"}:
            raise Refused("unknown_simulated_caller")
        suffix = caller[-1]
        context = SessionContext(uuid4().hex, 1, caller,
                                 frozenset({f"checking-{suffix}", f"savings-{suffix}", f"loan-{suffix}"}),
                                 monotonic() + 300)
        with self.lock:
            # Bound memory use in the single-user teaching process.
            if len(self.sessions) >= 32:
                raise Refused("session_limit")
            self.bank.open_session(context)
            token = token_urlsafe(32)
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
        prefix = b"Bearer "
        token = authorization[len(prefix):].decode("ascii", "ignore") if authorization.startswith(prefix) else ""
        if scope["path"].startswith("/host/"):
            allowed = compare_digest(token, self.registry.host_token)
        else:
            try:
                scope["banking_context"] = self.registry.context(token)
                allowed = True
            except Refused:
                allowed = False
        if not allowed:
            return await JSONResponse({"state": "refused"}, status_code=401)(scope, receive, send)
        if scope["path"].startswith("/mcp/"):
            # Do not let router redirects or alternate mounts skip raw validation.
            return await JSONResponse({"state": "refused"}, status_code=404)(scope, receive, send)
        if scope["path"] == "/mcp" and scope["method"] == "POST":
            # Validate raw tool arguments before SDK coercion/extra-field dropping.
            # No identity/confirmation input can sneak through an ignored field.
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
            import json
            try:
                payload = json.loads(captured)
            except (ValueError, UnicodeError):
                payload = None
            if not isinstance(payload, dict):
                # This endpoint accepts one JSON-RPC object, never a batch.
                return await JSONResponse({"jsonrpc": "2.0", "id": None,
                                           "error": {"code": -32600,
                                                     "message": "invalid_banking_request"}},
                                          status_code=400)(scope, receive, send)
            if payload.get("method") == "tools/call":
                try:
                    params = payload["params"]
                    tool = params["name"]
                    if tool not in CONTRACT["tools"]:
                        raise ValueError()
                    validate(tool, "input", params.get("arguments", {}))
                except Exception:
                    return await JSONResponse({"jsonrpc": "2.0", "id": payload.get("id"),
                                               "error": {"code": -32602,
                                                         "message": "invalid_banking_arguments"}})(scope, receive, send)
            body_sent = False
            upstream_receive = receive

            async def replay_body():
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {"type": "http.request", "body": bytes(captured), "more_body": False}
                return await upstream_receive()

            receive = replay_body
        return await self.app(scope, receive, send)


def create_app(profile, host_token, *, domain_fixture=True, fault="none"):
    if profile not in {"jack-henry", "fiserv"}:
        raise ValueError("unknown profile")
    if not isinstance(host_token, str) or len(host_token) < 32 or not host_token.isascii():
        raise ValueError("host capability must be at least 32 ASCII characters")
    registry = _Registry(host_token, profile, fault)
    server = _BankingMCP("banking-domain-simulator", host="127.0.0.1",
                     stateless_http=True, json_response=True)

    def invoke(ctx, tool, method, *args):
        context = ctx.request_context.request.scope["banking_context"]
        try:
            # Configuration names are not evidence that vendor adapters exist.
            registry.bank.accounts(context)
            if not domain_fixture:
                result = {"state": "unsupported", "reason": "vendor_contract_unqualified"}
            else:
                result = method(context, *args)
        except Refused as exc:
            result = {"state": "refused", "reason": str(exc)}
        return public_result(tool, profile, result)

    @server.tool(structured_output=True)
    def banking_accounts(ctx: Context) -> dict[str, object]:
        """Read permitted fictional account aliases; no caller identity argument."""
        return invoke(ctx, "banking_accounts", registry.bank.accounts)

    @server.tool(structured_output=True)
    def banking_balance(account: str, ctx: Context, balance_type: str = "available") -> dict[str, object]:
        """Read one permitted fictional balance, without write confirmation."""
        return invoke(ctx, "banking_balance", registry.bank.balance, account, balance_type)

    @server.tool(structured_output=True)
    def banking_history(account: str, ctx: Context, page: int = 1) -> dict[str, object]:
        """Read one page of our fictional shared banking history."""
        return invoke(ctx, "banking_history", registry.bank.history, account, page)

    @server.tool(structured_output=True)
    def banking_loan_payment(account: str, ctx: Context) -> dict[str, object]:
        """Read the supplied fictional next payment, never vendor data."""
        return invoke(ctx, "banking_loan_payment", registry.bank.loan_payment, account)

    @server.tool(structured_output=True)
    def banking_payoff(account: str, date: str, ctx: Context) -> dict[str, object]:
        """Read a supplied fictional quote date; other dates are unsupported."""
        return invoke(ctx, "banking_payoff", registry.bank.payoff, account, date)

    @server.tool(structured_output=True)
    def banking_review_transfer(source: str, destination: str, amount: str,
                                currency: str, ctx: Context) -> dict[str, object]:
        """Prepare exact fictional details. This never confirms or submits."""
        return invoke(ctx, "banking_review_transfer", registry.bank.review_transfer,
                      source, destination, amount, currency)

    @server.tool(structured_output=True)
    def banking_submit_transfer(review: str, ctx: Context) -> dict[str, object]:
        """Submit only a review confirmed separately by the trusted host."""
        return invoke(ctx, "banking_submit_transfer", registry.bank.submit, review)

    @server.tool(structured_output=True)
    def banking_transfer_status(review: str, ctx: Context) -> dict[str, object]:
        """Read the original retained outcome; never repeat a submission."""
        return invoke(ctx, "banking_transfer_status", registry.bank.status, review)

    app = server.streamable_http_app()

    async def host_control(request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise Refused("invalid_host_request")
            if request.url.path == "/host/open":
                return JSONResponse({"credential": registry.open(body.get("caller")),
                                     "identity": "simulated-only"})
            token = body.get("credential")
            context = registry.context(token) if isinstance(token, str) else None
            if context is None:
                raise Refused("invalid_host_binding")
            if request.url.path == "/host/confirm":
                registry.bank.confirm(context, body.get("review"), body.get("transfer"))
                return JSONResponse({"state": "confirmed"})
            if request.url.path == "/host/cancel":
                return JSONResponse(registry.bank.cancel(context, body.get("review")))
            if request.url.path == "/host/reset":
                registry.bank.reset(context)
                with registry.lock:
                    registry.sessions.pop(token, None)
                return JSONResponse({"state": "reset"})
        except Refused as exc:
            return JSONResponse({"state": "refused", "reason": str(exc)}, status_code=403)
        except Exception:
            return JSONResponse({"state": "refused", "reason": "invalid_host_request"}, status_code=400)
        return JSONResponse({"state": "refused"}, status_code=404)

    for path in ("/host/open", "/host/confirm", "/host/cancel", "/host/reset"):
        app.add_route(path, host_control, methods=["POST"])
    app.add_middleware(_Capabilities, registry=registry)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["jack-henry", "fiserv"], required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--domain-fixture", action="store_true",
                        help="Compatibility flag: all supported modes use our shared domain mock")
    parser.add_argument("--fault", choices=["none", "transfer-response-lost"], default="none",
                        help="Explicit fictional failure scenario, never a vendor fault")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("choose an unprivileged loopback port")
    token = os.environ.get("BANKING_HOST_CAPABILITY", "")
    if len(token) < 32 or not token.isascii():
        parser.error("a private ephemeral BANKING_HOST_CAPABILITY is required")
    import uvicorn
    uvicorn.run(create_app(args.profile, token, fault=args.fault),
                host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
