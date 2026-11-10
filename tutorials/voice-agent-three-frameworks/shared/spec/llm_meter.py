"""A local pass-through to the OpenAI API that times and prices every model call.

The three agents call OpenAI through three different client stacks (Rasa
through LiteLLM, LangGraph through langchain-openai, Strands through the
openai SDK). To measure their model calls the same way, the spec runner
points all of them at this meter with the standard environment variables
(``OPENAI_BASE_URL`` and ``OPENAI_API_BASE`` set to ``http://127.0.0.1:<port>/v1``)
and records, per request: when it started, the time to the first response
byte, the total time, the status, the model, and the token usage OpenAI
returned. Cost is computed from those tokens and the spec's price row.

What it changes: one thing. A streamed Chat Completions request that does not
already ask for usage gets ``stream_options: {"include_usage": true}``, so
OpenAI reports the tokens in a final chunk; without it a streamed call has no
usage to price. The flag is recorded per call (``injected_include_usage``).
Nothing else in a request or response is altered, and responses are relayed
as they arrive (a streamed response is relayed chunk by chunk).

What it never does: log a header, a key or a message body. Only the fields
above are written. It listens on 127.0.0.1 only.

Stdlib only.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

UPSTREAM = "https://api.openai.com"
_HOP_HEADERS = {"host", "content-length", "connection", "accept-encoding", "transfer-encoding", "keep-alive",
                "proxy-connection", "te", "upgrade"}


def usage_from(body: Any) -> dict:
    """Token counts from a Chat Completions or Responses usage block."""
    usage = (body or {}).get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return {}
    prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
    completion = usage.get("completion_tokens", usage.get("output_tokens"))
    details_in = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
    details_out = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cached_tokens": details_in.get("cached_tokens"),
        "reasoning_tokens": details_out.get("reasoning_tokens"),
    }


def cost_usd(usage: dict, prices: dict) -> Optional[float]:
    if not usage or usage.get("prompt_tokens") is None or usage.get("completion_tokens") is None:
        return None
    cached = usage.get("cached_tokens") or 0
    fresh = usage["prompt_tokens"] - cached
    return round((fresh * prices["usd_per_1m_input_tokens"] + cached * prices["usd_per_1m_cached_input_tokens"]
                  + usage["completion_tokens"] * prices["usd_per_1m_output_tokens"]) / 1e6, 6)


class _SSEUsage:
    """Collects the usage block from a server-sent-events stream as it passes."""

    def __init__(self) -> None:
        self.buffer = b""
        self.usage: dict = {}
        self.model: Optional[str] = None
        #: The stream's end is in: ``[DONE]`` (Chat Completions) or a final Responses event.
        self.done = False

    def feed(self, chunk: bytes) -> None:
        self.buffer += chunk
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                self.done = True
                continue
            try:
                event = json.loads(data)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") in ("response.completed", "response.failed", "response.incomplete"):
                self.done = True
            # Responses API: the usage is on the completed response.
            source = event.get("response") if isinstance(event.get("response"), dict) else event
            found = usage_from(source)
            if found.get("prompt_tokens") is not None:
                self.usage = found
            self.model = self.model or source.get("model")


class LLMMeter:
    """Run with ``start()``; read ``rows`` or the JSONL file; ``stop()`` at the end."""

    def __init__(self, prices: dict, log_path: Optional[Path] = None, port: int = 0,
                 upstream: str = UPSTREAM, model_id: Optional[str] = None,
                 reasoning_effort: Optional[str] = None) -> None:
        self.prices = prices
        self.model_id = model_id
        self.reasoning_effort = reasoning_effort
        parts = urlsplit(upstream)
        self._upstream_https = parts.scheme == "https"
        self._upstream_host = parts.hostname or "api.openai.com"
        self._upstream_port = parts.port or (443 if self._upstream_https else 80)
        self.log_path = log_path
        self.rows: list[dict] = []
        self._lock = threading.Lock()
        meter = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: Any) -> None:  # silence the default access log
                return

            def do_POST(self) -> None:
                meter._relay(self, "POST")

            def do_GET(self) -> None:
                meter._relay(self, "GET")

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self._thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def env(self) -> dict:
        """What to add to an agent process's environment to route it through the meter."""
        return {"OPENAI_BASE_URL": self.base_url, "OPENAI_API_BASE": self.base_url}

    def start(self) -> "LLMMeter":
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def total_cost(self) -> float:
        with self._lock:
            return round(sum(r.get("cost_usd") or 0 for r in self.rows), 6)

    def rows_between(self, start: float, end: float) -> list[dict]:
        with self._lock:
            return [r for r in self.rows if start <= r["ts_start"] < end]

    def _record(self, row: dict) -> None:
        with self._lock:
            self.rows.append(row)
            if self.log_path is not None:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row) + "\n")

    def _relay(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        started = time.time()
        length = int(handler.headers.get("Content-Length") or 0)
        raw = handler.rfile.read(length) if length else b""
        injected = False
        body = None
        model = None
        stream = False
        if raw:
            try:
                body = json.loads(raw)
            except ValueError:
                body = None
            if isinstance(body, dict):
                model = body.get("model")
                stream = bool(body.get("stream"))
                if stream and handler.path.rstrip("/").endswith("/chat/completions") and \
                        not (body.get("stream_options") or {}).get("include_usage"):
                    body["stream_options"] = {**(body.get("stream_options") or {}), "include_usage": True}
                    raw = json.dumps(body).encode()
                    injected = True
        if isinstance(body, dict) and method == "POST" and handler.path.rstrip("/").endswith(("/responses", "/chat/completions")):
            reasoning = body.get("reasoning") or {}
            effort = reasoning.get("effort") if isinstance(reasoning, dict) else None
            effort = effort or body.get("reasoning_effort")
            wrong_model = self.model_id is not None and model != self.model_id
            wrong_effort = self.reasoning_effort is not None and effort != self.reasoning_effort
            if wrong_model or wrong_effort:
                ended = time.time()
                self._record({"ts_start": round(started, 6), "ts_end": round(ended, 6),
                    "path": handler.path, "method": method, "model": model,
                    "reasoning_effort": effort, "status": 409,
                    "error_code": "benchmark_contract_mismatch", "cost_usd": 0.0,
                    "duration_ms": round((ended-started)*1000, 1), "upstream_called": False})
                payload = json.dumps({"error": {"message": "Benchmark requires the pinned model and reasoning effort; no upstream request made",
                    "type": "benchmark_contract_mismatch", "code": "benchmark_contract_mismatch"}}).encode()
                handler.send_response(409)
                handler.send_header("Content-Type", "application/json")
                handler.send_header("Content-Length", str(len(payload)))
                handler.end_headers()
                handler.wfile.write(payload)
                return
        headers = {k: v for k, v in handler.headers.items() if k.lower() not in _HOP_HEADERS}
        headers["Host"] = self._upstream_host
        headers["Accept-Encoding"] = "identity"
        if raw:
            headers["Content-Length"] = str(len(raw))
        row: dict = {"ts_start": round(started, 6), "path": handler.path, "method": method, "model": model,
                     "stream": stream, "injected_include_usage": injected,
                     "reasoning_effort": ((body.get("reasoning") or {}).get("effort") or body.get("reasoning_effort")) if isinstance(body, dict) else None}
        connection = http.client.HTTPSConnection if self._upstream_https else http.client.HTTPConnection
        upstream = connection(self._upstream_host, self._upstream_port, timeout=180)
        recorded = False

        def finish(first_byte: Optional[float]) -> None:
            # Recorded before the client's last bytes go out: a client that has the whole
            # response must find its row (the runner reads the rows as soon as a call ends).
            nonlocal recorded
            ended = time.time()
            row["ttfb_ms"] = round(((first_byte or ended) - started) * 1000, 1)
            row["duration_ms"] = round((ended - started) * 1000, 1)
            row["ts_end"] = round(ended, 6)
            row["cost_usd"] = cost_usd(row.get("usage") or {}, self.prices)
            self._record(row)
            recorded = True

        try:
            upstream.request(method, handler.path, body=raw or None, headers=headers)
            response = upstream.getresponse()
            first_byte: Optional[float] = None
            row["status"] = response.status
            content_type = response.getheader("Content-Type", "")
            handler.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in _HOP_HEADERS and key.lower() != "content-encoding":
                    handler.send_header(key, value)
            if "text/event-stream" in content_type:
                handler.send_header("Transfer-Encoding", "chunked")
                handler.end_headers()
                sse = _SSEUsage()
                while True:
                    chunk = response.read1(65536)
                    if not chunk:
                        break
                    first_byte = first_byte or time.time()
                    sse.feed(chunk)
                    if sse.done:
                        # The usage is in: record before the stream's last bytes reach the client.
                        row["usage"] = sse.usage
                        row["model"] = sse.model or model
                        finish(first_byte)
                    handler.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    handler.wfile.flush()
                if not recorded:
                    row["usage"] = sse.usage
                    row["model"] = sse.model or model
                    finish(first_byte)
                handler.wfile.write(b"0\r\n\r\n")
                handler.wfile.flush()
            else:
                payload = response.read()
                first_byte = time.time()
                try:
                    parsed = json.loads(payload) if payload else None
                except ValueError:
                    parsed = None
                row["usage"] = usage_from(parsed)
                if isinstance(parsed, dict):
                    row["model"] = parsed.get("model") or model
                    if response.status >= 400 and isinstance(parsed.get("error"), dict):
                        row["error_code"] = parsed["error"].get("code") or parsed["error"].get("type")
                finish(first_byte)
                handler.send_header("Content-Length", str(len(payload)))
                handler.end_headers()
                handler.wfile.write(payload)
                handler.wfile.flush()
        except Exception as exc:  # recorded, then surfaced to the client as a 502
            row.update({"status": 502, "error_code": f"meter: {type(exc).__name__}", "ts_end": round(time.time(), 6),
                        "duration_ms": round((time.time() - started) * 1000, 1), "cost_usd": None})
            try:
                message = json.dumps({"error": {"message": "llm meter could not reach the upstream API",
                                                "type": "meter_upstream_error"}}).encode()
                handler.send_response(502)
                handler.send_header("Content-Type", "application/json")
                handler.send_header("Content-Length", str(len(message)))
                handler.end_headers()
                handler.wfile.write(message)
            except Exception:
                pass
        finally:
            upstream.close()
            if not recorded:
                self._record(row)
