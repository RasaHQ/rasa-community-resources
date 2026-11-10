"""Exercise the actual CLI main with a real ephemeral HTTP server."""
import json
from http.server import HTTPServer
from threading import Thread
from urllib.request import Request, urlopen
import unittest
from unittest.mock import patch
from typesafe_sdk import TypeSafeClient
from jacaranda_jev import server


class WorkerLifecycle(unittest.TestCase):
    def test_default_main_reuses_one_real_client_and_closes_it(self):
        clients = []
        requests = []
        closed = []
        def client(**kwargs):
            self.assertEqual(kwargs["api_key"], "scripted-local-test")
            self.assertEqual(kwargs["base_url"], "https://scripted.invalid")
            self.assertIsNotNone(kwargs["transport"])
            native = TypeSafeClient(**kwargs)
            clients.append(native)
            original_call = native.system_one
            original_close = native.close
            def call(*args, **kw):
                requests.append(kw)
                return original_call(*args, **kw)
            def close():
                closed.append(True)
                original_close()
            native.system_one = call
            native.close = close
            return native

        class ControlledServer:
            def __init__(self, address, handler):
                self.native = HTTPServer((address[0], 0), handler)
            def __enter__(self):
                return self
            def __exit__(self, *_):
                self.native.server_close()
            def serve_forever(self):
                thread = Thread(target=self.native.serve_forever, daemon=True)
                thread.start()
                try:
                    for message in ["Current", "Current again"]:
                        body = {"owner": "demo-a", "conversation": "main-test", "message": message}
                        req = Request(f"http://127.0.0.1:{self.native.server_port}/propose",
                                      data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
                        with urlopen(req, timeout=3) as response:
                            assert json.load(response)["status"] == "account_proposal"
                finally:
                    self.native.shutdown()
                    thread.join(timeout=3)

        with patch.object(server, "TypeSafeClient", side_effect=client), \
                patch.object(server, "HTTPServer", ControlledServer), \
                patch("sys.argv", ["account-worker"]), \
                patch.dict("os.environ", {"TYPESAFE_API_KEY": "must-not-be-read-in-scripted-mode"}):
            server.main()
        self.assertEqual(len(clients), 1)
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(closed), 1)
