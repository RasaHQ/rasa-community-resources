"""Synthetic loopback fixtures; never send real chat or provider requests."""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay import local_json


@contextmanager
def server(redirect=None):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            seen.append((self.command, self.path, body))
            self.send_response(302 if redirect else 200)
            if redirect:
                self.send_header("Location", redirect)
            self.end_headers()
            self.wfile.write(json.dumps({"fixture": "fictional-only"}).encode())

        do_POST = do_GET

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: http.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}", seen
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)


class NetworkControls(unittest.TestCase):
    def test_chat_and_tracker_ignore_inherited_proxy(self):
        with server() as (proxy, intercepted), server() as (origin, delivered):
            env = {"HTTP_PROXY": proxy, "http_proxy": proxy,
                   "ALL_PROXY": proxy, "all_proxy": proxy,
                   "NO_PROXY": "", "no_proxy": ""}
            with patch.dict(os.environ, env):
                request = urllib.request.Request(origin + "/webhooks/rest/webhook",
                                                 data=b'{"message":"fictional-only"}')
                self.assertEqual(local_json(request), {"fixture": "fictional-only"})
                self.assertEqual(local_json(origin + "/conversations/demo/tracker"),
                                 {"fixture": "fictional-only"})
            self.assertEqual(intercepted, [])
            self.assertEqual([row[0] for row in delivered], ["POST", "GET"])
            self.assertEqual(delivered[0][2], b'{"message":"fictional-only"}')

    def test_chat_and_tracker_never_follow_redirects(self):
        with server() as (destination, followed), server(destination + "/capture") as (origin, seen):
            for request in (origin + "/conversations/demo/tracker",
                            urllib.request.Request(origin + "/webhooks/rest/webhook", data=b"fictional-only")):
                with self.subTest(request=request):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        local_json(request)
                    self.assertEqual(error.exception.code, 302)
                    error.exception.close()
            self.assertEqual(followed, [])
            self.assertEqual(len(seen), 2)

    def test_non_loopback_request_is_rejected_before_opening(self):
        with patch("urllib.request.build_opener") as build:
            with self.assertRaises(ValueError):
                local_json("http://example.invalid/tracker")
            build.assert_not_called()
