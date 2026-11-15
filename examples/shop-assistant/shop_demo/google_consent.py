"""One-time Desktop OAuth consent, with credentials kept in memory."""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import socket
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr

SCOPE = "https://www.googleapis.com/auth/spreadsheets"
PORT = 8766
REDIRECT = f"http://127.0.0.1:{PORT}/"


class DesktopClient(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    client_id: str
    client_secret: SecretStr
    auth_uri: str
    token_uri: str


def client_config(value):
    raw = json.loads(value)
    client = DesktopClient.model_validate(raw["installed"])
    if (not client.client_id.endswith(".apps.googleusercontent.com")
            or client.auth_uri not in {"https://accounts.google.com/o/oauth2/auth", "https://accounts.google.com/o/oauth2/v2/auth"}
            or client.token_uri != "https://oauth2.googleapis.com/token"):
        raise ValueError("Use an unmodified Google Desktop OAuth client")
    return {"installed": client.model_dump() | {"client_secret": client.client_secret.get_secret_value()}}


def callback_code(path, state):
    url = urlsplit(path)
    query = parse_qs(url.query, keep_blank_values=True)
    if url.path != "/" or url.fragment or url.scheme or url.netloc:
        raise ValueError("Unexpected callback path")
    if len(query.get("state", [])) != 1 or not hmac.compare_digest(query["state"][0], state):
        raise ValueError("The consent state did not match")
    if "error" in query or len(query.get("code", [])) != 1 or not query["code"][0]:
        raise ValueError("Consent was not granted")
    return query["code"][0]


def receive_code(state, *, ready, timeout=300, alive=lambda: True):
    result = []
    deadline = time.monotonic() + timeout

    class Server(HTTPServer):
        active = None

        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(max(.01, min(5, deadline - time.monotonic())))
            self.active = connection
            if time.monotonic() >= deadline or not alive():
                connection.close()
                raise TimeoutError("The consent window has closed")
            return connection, address

        def close_request(self, request):
            super().close_request(request)
            if self.active is request:
                self.active = None

        def handle_error(self, request, client_address):
            # Do not print a request URL or code from a failed HTTP handler.
            pass

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            try:
                if time.monotonic() >= deadline or not alive():
                    raise ValueError("The consent window has closed")
                code = callback_code(self.path, state)
            except ValueError:
                self.send_error(400, "Invalid consent callback")
                return
            result.append(code)
            body = b"Consent received. Return to the Codespace terminal."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with Server(("127.0.0.1", PORT), Handler) as server:
        server.timeout = 1
        finished = threading.Event()

        def enforce_deadline():
            while not finished.wait(.05):
                if time.monotonic() >= deadline or not alive():
                    server.socket.close()
                    connection = server.active
                    if connection is not None:
                        try:
                            connection.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                        connection.close()
                    return

        watcher = threading.Thread(target=enforce_deadline, daemon=True)
        watcher.start()
        try:
            ready()
            while not result and alive() and time.monotonic() < deadline:
                try:
                    server.handle_request()
                except (OSError, ValueError):
                    if time.monotonic() >= deadline or not alive():
                        break
                    raise
        finally:
            finished.set()
            watcher.join(1)
    if not result:
        raise TimeoutError("Consent timed out; start a new attempt")
    return result[0]


def main():
    # No client file, token file, dotenv, browser automation, or public callback.
    from google_auth_oauthlib.flow import InstalledAppFlow
    try:
        config = client_config(os.environ["GOOGLE_CLIENT_SECRETS_JSON"])
        flow = InstalledAppFlow.from_client_config(config, [SCOPE],
            redirect_uri=REDIRECT, autogenerate_code_verifier=True)
        url, state = flow.authorization_url(prompt="consent", access_type="offline")

        def ready():
            print("Keep the private laptop-to-Codespace port forward running on port 8766.", flush=True)
            print("Open this URL in your laptop browser; finish consent within five minutes:", flush=True)
            print(url, flush=True)

        connected = threading.Event()
        connected.set()

        def watch_terminal():
            # A raw descriptor read avoids a daemon thread retaining Python's
            # buffered-stdin lock while the interpreter shuts down.
            while os.read(sys.stdin.fileno(), 1):
                pass
            connected.clear()

        threading.Thread(target=watch_terminal, daemon=True).start()
        code = receive_code(state, ready=ready, alive=connected.is_set)
        flow.fetch_token(code=code, timeout=30)
        if not flow.credentials.refresh_token:
            raise ValueError("Google did not return an offline refresh token")
        # Printing is explicit: the operator transfers this directly to a Codespace secret.
        print("Store the following line as GOOGLE_TOKEN_JSON in your Codespace secrets:")
        print(flow.credentials.to_json(), flush=True)
    except (Exception, KeyboardInterrupt):
        print("Consent did not complete. No credential file was written; start a new attempt.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
