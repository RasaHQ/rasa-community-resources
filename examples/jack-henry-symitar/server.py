# SPDX-License-Identifier: MIT
"""Example-local MCP transport; the trusted channel supplies a scoped host.

No framework or sibling application is imported. This module implements the
JSON response form of Streamable HTTP, protocol 2025-06-18. It does not create
sessions, authenticate bank customers, confirm transfers, or call a vendor.
The host must enforce those policies and return only minimized public results.
Protocol: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
import hmac
import json
import re
import socket
from typing import Protocol

MAX_REQUEST = 32_768
MAX_RESULT = 16_384
PROTOCOL = "2025-06-18"
ALIAS = {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,31}$"}
DAY = {"type": "string", "format": "date"}
AMOUNT = {"type": "string", "pattern": "^(?:0|[1-9][0-9]{0,6})\\.[0-9]{2}$"}


def tool(name, description, properties=None):
    properties = properties or {}
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties,
                            "required": list(properties), "additionalProperties": False}}


TOOLS = (
    tool("banking_accounts", "List the current fictional principal's permitted account aliases."),
    tool("banking_balance", "Read an available balance for a permitted account alias.", {"account": ALIAS}),
    tool("banking_history", "Read at most twenty fictional transactions within inclusive dates.",
         {"account": ALIAS, "start_date": DAY, "end_date": DAY}),
    tool("banking_loan_payment", "Read current payment due and next due date as separate facts.", {"loan": ALIAS}),
    tool("banking_payoff", "Request a dated fictional payoff quote; this does not pay a loan.",
         {"loan": ALIAS, "payoff_date": DAY}),
    tool("banking_review_transfer", "Prepare a transfer review. This never sends a transfer.",
         {"source": ALIAS, "destination": ALIAS, "amount": AMOUNT}),
    tool("banking_transfer_status", "Read this principal's latest retained local transfer outcome."),
)
SCHEMAS = {item["name"]: item["inputSchema"] for item in TOOLS}


class ScopedHost(Protocol):
    """Constructed by the trusted channel, never from model arguments.

    Each call must recheck host authority and unresolved holds. A transfer
    review is only a proposal; output delivery and next-user confirmation are
    separate private adapter operations, absent from this interface.
    """
    def call(self, name: str, arguments: dict) -> object: ...


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("nonfinite")


def _arguments(name, arguments):
    schema = SCHEMAS.get(name)
    if schema is None or type(arguments) is not dict or set(arguments) != set(schema["required"]):
        raise ValueError("invalid_arguments")
    for key, rule in schema["properties"].items():
        value = arguments[key]
        if type(value) is not str or len(value) > 64:
            raise ValueError("invalid_arguments")
        if "pattern" in rule and re.fullmatch(rule["pattern"], value) is None:
            raise ValueError("invalid_arguments")
        if rule.get("format") == "date":
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
                raise ValueError("invalid_date")
            date.fromisoformat(value)
    if name == "banking_history" and (arguments["start_date"] > arguments["end_date"] or
            (date.fromisoformat(arguments["end_date"]) - date.fromisoformat(arguments["start_date"])).days > 366):
        raise ValueError("invalid_date_range")
    if name == "banking_review_transfer" and (arguments["source"] == arguments["destination"] or arguments["amount"] == "0.00"):
        raise ValueError("invalid_intent")


def error(identifier, code, message):
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


class MCP:
    def __init__(self, host: ScopedHost):
        self._host = host

    def handle(self, raw: bytes):
        """Return a JSON-RPC result or None for accepted notifications.

        Notifications cannot invoke tools. Parsing and validation precede the
        only host call, so raw JSON types cannot be coerced by a client schema.
        """
        try:
            if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST:
                raise ValueError("oversize")
            message = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_nonfinite)
        except (ValueError, UnicodeError, RecursionError):
            return error(None, -32700, "Invalid JSON")
        if type(message) is not dict or message.get("jsonrpc") != "2.0":
            return error(None, -32600, "Invalid request")
        identifier = message.get("id")
        if "id" in message and identifier is None:
            return error(None, -32600, "Null request id is not supported")
        if identifier is not None and (type(identifier) not in {str, int} or isinstance(identifier, str) and len(identifier) > 128):
            return error(None, -32600, "Invalid request id")
        method, params = message.get("method"), message.get("params", {})
        if type(method) is not str or type(params) is not dict or set(message) - {"jsonrpc", "id", "method", "params"}:
            return error(identifier, -32600, "Invalid request")
        if "id" not in message:
            if method in {"notifications/initialized", "notifications/cancelled"}:
                return None
            return error(None, -32600, "Unsupported notification")
        if method == "initialize":
            if type(params.get("protocolVersion")) is not str or type(params.get("capabilities")) is not dict or type(params.get("clientInfo")) is not dict:
                return error(identifier, -32602, "Invalid initialization")
            result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "fictional-symitar", "version": "0.1.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            if params:
                return error(identifier, -32602, "No pagination cursor supported")
            result = {"tools": deepcopy(TOOLS)}
        elif method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments", {})
            try:
                if type(name) is not str or set(params) - {"name", "arguments"}:
                    raise ValueError("invalid_call")
                _arguments(name, arguments)
            except (ValueError, TypeError):
                return error(identifier, -32602, "Invalid tool or arguments")
            try:
                # Copy validated values before private host dispatch.
                data = self._host.call(name, dict(arguments))
                text = json.dumps(data, allow_nan=False, separators=(",", ":"))
                if len(text.encode()) > MAX_RESULT:
                    raise ValueError("oversize_result")
                result = {"content": [{"type": "text", "text": text}], "isError": False}
            except Exception:
                # No exception text, credential, raw vendor body or traceback.
                result = {"content": [{"type": "text", "text": "Request unavailable or refused."}], "isError": True}
        else:
            return error(identifier, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": identifier, "result": result}


def local_server(host: ScopedHost, bearer: str, port: int = 0) -> HTTPServer:
    """Bind loopback only; one scoped host and serialized request at a time.

    The trusted launcher injects a private random bearer into its MCP client.
    The model never receives it. HTTP origin/host checks are independent of it.
    No unauthenticated health, reset, confirmation or session endpoint exists.
    Caller owns server_close/shutdown and the serving thread/process lifetime.
    """
    if not isinstance(bearer, str) or re.fullmatch(r"[A-Za-z0-9_-]{32,128}", bearer) is None:
        raise ValueError("private_bearer_required")
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("invalid_port")
    protocol = MCP(host)

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, *args):
            pass  # Never record headers, tool inputs or financial payloads.

        def finish_response(self, status, data=None):
            raw = b"" if data is None else json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            if raw:
                self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(raw)
            self.close_connection = True

        def authorized(self):
            expected_host = "127.0.0.1:" + str(self.server.server_port)
            if self.path != "/mcp" or self.headers.get_all("Host") != [expected_host] or self.headers.get_all("Origin"):
                self.finish_response(403)
                return False
            values = self.headers.get_all("Authorization")
            if values is None or len(values) != 1 or not hmac.compare_digest(values[0].encode("utf-8"), ("Bearer " + bearer).encode("ascii")):
                self.finish_response(401)
                return False
            return True

        def do_GET(self):
            if self.authorized():
                self.finish_response(405)  # This server does not offer SSE.

        def do_DELETE(self):
            if self.authorized():
                self.finish_response(405)

        def do_POST(self):
            if not self.authorized():
                return
            versions = self.headers.get_all("MCP-Protocol-Version")
            if versions is not None and versions != [PROTOCOL]:
                self.finish_response(400)
                return
            accepted = {part.strip().split(";", 1)[0] for part in self.headers.get("Accept", "").split(",")}
            if not {"application/json", "text/event-stream"} <= accepted:
                self.finish_response(406)
                return
            if self.headers.get_all("Transfer-Encoding") or self.headers.get_all("Content-Length") is None or len(self.headers.get_all("Content-Length")) != 1:
                self.finish_response(400)
                return
            try:
                if re.fullmatch(r"[0-9]+", self.headers["Content-Length"]) is None:
                    raise ValueError("invalid_size")
                size = int(self.headers["Content-Length"])
                if not 0 < size <= MAX_REQUEST:
                    raise ValueError("invalid_size")
                if self.headers.get_content_type() != "application/json":
                    self.finish_response(415)
                    return
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("short_body")
            except (ValueError, socket.timeout, OSError):
                self.finish_response(400)
                return
            result = protocol.handle(raw)
            self.finish_response(202 if result is None else 200, result)

    return HTTPServer(("127.0.0.1", port), Handler)
