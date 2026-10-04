#!/usr/bin/env python3
"""Serve the voice page, and relay its WebSocket to an agent with a conversation id.

    python3 shared/web/serve.py rasa                         # agent at http://127.0.0.1:5005
    python3 shared/web/serve.py langgraph --agent http://127.0.0.1:5006
    open http://127.0.0.1:8765/

Stdlib only. Three routes besides the static files:

- ``GET /relay?sender=<id>``: a WebSocket. The server opens its own WebSocket
  to the agent's browser_audio endpoint with ``X-Rasa-Sender-Id: <id>`` (a
  header a browser cannot set on a WebSocket), then copies bytes both ways
  untouched. Client frames stay masked and server frames unmasked, as the
  protocol requires in each direction, so nothing needs re-framing.
- ``GET /api/events?sender=<id>``: the conversation's user and bot messages,
  read from the agent's events endpoint (Rasa: the tracker), for the
  transcript view.
- ``GET /api/config``: which agent the relay points at.

Neither route changes the protocol: the page speaks browser_audio exactly as
it would to the agent directly. Listens on 127.0.0.1 only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
SENDER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

PRESETS = {
    "rasa": {"agent": "http://127.0.0.1:5005", "events_path": "/conversations/{id}/tracker"},
    "langgraph": {"agent": "http://127.0.0.1:5006", "events_path": "/conversations/{id}/events"},
    "strands": {"agent": "http://127.0.0.1:5007", "events_path": "/conversations/{id}/events"},
}
for _name, _port in (("langchain", 5008), ("agno", 5009), ("crewai", 5010),
                     ("pipecat", 5011), ("livekit", 5012)):
    PRESETS[_name] = {"agent": f"http://127.0.0.1:{_port}",
                      "events_path": "/conversations/{id}/events"}

WS_PATH = "/webhooks/browser_audio/websocket"


def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def open_upstream(agent: str, ws_path: str, sender: str) -> tuple[socket.socket, bytes]:
    """WebSocket handshake with the agent; returns the socket and any bytes read past the 101."""
    parts = urlsplit(agent)
    host, port = parts.hostname or "127.0.0.1", parts.port or 80
    sock = socket.create_connection((host, port), timeout=10)
    key = base64.b64encode(os.urandom(16)).decode()
    request = (f"GET {ws_path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nX-Rasa-Sender-Id: {sender}\r\n\r\n")
    sock.sendall(request.encode())
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("agent closed during the WebSocket upgrade")
        response += chunk
    head, _, rest = response.partition(b"\r\n\r\n")
    status = head.split(b"\r\n", 1)[0].decode("latin-1")
    if " 101 " not in f"{status} ":
        raise ConnectionError(f"agent refused the upgrade: {status}")
    if accept_key(key).encode() not in head:
        raise ConnectionError("agent sent a bad Sec-WebSocket-Accept")
    sock.settimeout(None)
    return sock, rest


def pipe(src: socket.socket, dst: socket.socket, done: threading.Event) -> None:
    try:
        while not done.is_set():
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        done.set()
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


class Handler(SimpleHTTPRequestHandler):
    # A browser accepts a WebSocket upgrade only as "HTTP/1.1 101".
    protocol_version = "HTTP/1.1"
    config: dict = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def log_message(self, fmt, *args):  # quieter than the default: no transcript polling
        if "/api/events" not in str(args[0] if args else ""):
            super().log_message(fmt, *args)

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if url.path == "/relay":
            return self._relay(query.get("sender", [""])[0])
        if url.path == "/api/config":
            return self._json(200, {"relay": True, **{k: self.config[k] for k in ("agent", "framework", "ws_path")}})
        if url.path == "/api/events":
            return self._events(query.get("sender", [""])[0])
        if url.path.endswith((".py", ".md")):
            return self._json(404, {"error": "not served"})
        return super().do_GET()

    def _events(self, sender: str) -> None:
        if not SENDER_RE.fullmatch(sender):
            return self._json(400, {"error": "bad sender id"})
        url = self.config["agent"] + self.config["events_path"].format(id=sender)
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                doc = json.loads(response.read() or b"{}")
        except Exception as exc:
            return self._json(502, {"error": f"agent events unavailable: {type(exc).__name__}"})
        events = [{"event": e.get("event"), "text": e.get("text"), "timestamp": e.get("timestamp")}
                  for e in doc.get("events", []) if e.get("event") in ("user", "bot")
                  and not str(e.get("text") or "").startswith("/session_")]
        return self._json(200, {"sender": sender, "events": events})

    def _relay(self, sender: str) -> None:
        if self.headers.get("Upgrade", "").lower() != "websocket" or not self.headers.get("Sec-WebSocket-Key"):
            return self._json(400, {"error": "expected a WebSocket upgrade"})
        if not SENDER_RE.fullmatch(sender):
            return self._json(400, {"error": "bad sender id"})
        try:
            upstream, early = open_upstream(self.config["agent"], self.config["ws_path"], sender)
        except Exception as exc:
            return self._json(502, {"error": f"agent unavailable: {exc}"})
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept_key(self.headers["Sec-WebSocket-Key"]))
        self.end_headers()
        self.wfile.flush()
        client = self.connection
        client.settimeout(None)
        if early:
            client.sendall(early)
        done = threading.Event()
        back = threading.Thread(target=pipe, args=(upstream, client, done), daemon=True)
        back.start()
        pipe(client, upstream, done)
        back.join(timeout=5)
        upstream.close()
        self.close_connection = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("framework", choices=sorted(PRESETS), nargs="?", default="rasa")
    parser.add_argument("--agent", help="agent base URL (default per framework)")
    parser.add_argument("--events-path", help="conversation events path with {id} (default per framework)")
    parser.add_argument("--ws-path", default=WS_PATH)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    preset = PRESETS[args.framework]
    Handler.config = {"framework": args.framework, "agent": (args.agent or preset["agent"]).rstrip("/"),
                      "events_path": args.events_path or preset["events_path"], "ws_path": args.ws_path}
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    print(f"voice page on http://127.0.0.1:{server.server_address[1]}/  ->  {Handler.config['agent']} "
          f"({args.framework})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
