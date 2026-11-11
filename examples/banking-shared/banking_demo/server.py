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

from .service import BankingService, Refused, SessionContext


class _DomainFixture:
    """Explicit domain data only; no vendor fields, network or real accounts."""

    def balance(self, account):
        return {"amount": "100.00", "currency": "USD"}

    def submit(self, operation, transfer):
        return "queued"


class _Registry:
    def __init__(self, host_token):
        self.host_token = host_token
        self.bank = BankingService(_DomainFixture())
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
                                 frozenset({f"checking-{suffix}", f"savings-{suffix}"}),
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
        return await self.app(scope, receive, send)


def create_app(profile, host_token, *, domain_fixture=False):
    if profile not in {"jack-henry", "fiserv"}:
        raise ValueError("unknown profile")
    if not isinstance(host_token, str) or len(host_token) < 32 or not host_token.isascii():
        raise ValueError("host capability must be at least 32 ASCII characters")
    registry = _Registry(host_token)
    server = FastMCP("banking-domain-simulator", host="127.0.0.1",
                     stateless_http=True, json_response=True)

    def invoke(ctx, method, *args):
        context = ctx.request_context.request.scope["banking_context"]
        try:
            # Configuration names are not evidence that vendor adapters exist.
            registry.bank.accounts(context)
            if not domain_fixture:
                return {"state": "unsupported", "reason": "vendor_contract_unqualified"}
            result = method(context, *args)
            return {"fixture": "domain-only", **result}
        except Refused as exc:
            return {"state": "refused", "reason": str(exc)}

    @server.tool()
    def banking_accounts(ctx: Context) -> dict:
        """Read permitted fictional account aliases; no caller identity argument."""
        return invoke(ctx, registry.bank.accounts)

    @server.tool()
    def banking_balance(account: str, ctx: Context) -> dict:
        """Read one permitted fictional balance, without write confirmation."""
        return invoke(ctx, registry.bank.balance, account)

    def unsupported(ctx, account):
        # Ownership/assurance still applies to unsupported read capabilities.
        result = invoke(ctx, registry.bank.balance, account)
        if result.get("state") in {"refused", "unsupported"}:
            return result
        return {"state": "unsupported", "reason": "contract_not_implemented"}

    @server.tool()
    def banking_history(account: str, ctx: Context) -> dict:
        """History is unsupported until the selected contract is implemented."""
        return unsupported(ctx, account)

    @server.tool()
    def banking_loan_payment(account: str, ctx: Context) -> dict:
        """Loan schedule is unsupported until its contract is implemented."""
        return unsupported(ctx, account)

    @server.tool()
    def banking_payoff(account: str, date: str, ctx: Context) -> dict:
        """Dated payoff is unsupported; no quote is invented."""
        return unsupported(ctx, account)

    @server.tool()
    def banking_review_transfer(source: str, destination: str, amount: str,
                                currency: str, ctx: Context) -> dict:
        """Prepare exact fictional details. This never confirms or submits."""
        return invoke(ctx, registry.bank.review_transfer, source, destination, amount, currency)

    @server.tool()
    def banking_submit_transfer(review: str, ctx: Context) -> dict:
        """Submit only a review confirmed separately by the trusted host."""
        return invoke(ctx, registry.bank.submit, review)

    @server.tool()
    def banking_transfer_status(review: str, ctx: Context) -> dict:
        """Read the original retained outcome; never repeat a submission."""
        return invoke(ctx, registry.bank.status, review)

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
                        help="Explicit fictional domain controls, not vendor contracts")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("choose an unprivileged loopback port")
    token = os.environ.get("BANKING_HOST_CAPABILITY", "")
    if len(token) < 32 or not token.isascii():
        parser.error("a private ephemeral BANKING_HOST_CAPABILITY is required")
    import uvicorn
    uvicorn.run(create_app(args.profile, token, domain_fixture=args.domain_fixture),
                host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
