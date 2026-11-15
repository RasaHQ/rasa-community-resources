import json
import threading
import socket
import time
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from shop_demo.google_consent import PORT, callback_code, client_config, receive_code


class ConsentTests(unittest.TestCase):
    def test_silent_trickled_and_disconnected_peers_cannot_keep_listener_open(self):
        for case in ("silent", "trickle", "disconnect"):
            with self.subTest(case=case):
                ready, connected = threading.Event(), threading.Event()
                connected.set()
                outcome = []

                def receive():
                    try:
                        receive_code("right", ready=ready.set,
                            timeout=3 if case == "disconnect" else .35, alive=connected.is_set)
                    except TimeoutError:
                        outcome.append("closed")

                worker = threading.Thread(target=receive)
                worker.start()
                self.assertTrue(ready.wait(2))
                with socket.create_connection(("127.0.0.1", PORT), timeout=1) as connection:
                    if case == "trickle":
                        for byte in b"GET /?state=right&code=unfinished":
                            try:
                                connection.sendall(bytes([byte]))
                            except OSError:
                                break
                            time.sleep(.06)
                    elif case == "disconnect":
                        connection.sendall(b"GET / HTTP/1.1\r\nHost:")
                        connected.clear()
                    worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(outcome, ["closed"])
                with socket.socket() as probe:
                    probe.settimeout(.2)
                    self.assertNotEqual(probe.connect_ex(("127.0.0.1", PORT)), 0)

    def test_absolute_deadline_closes_a_partial_http_request(self):
        ready = threading.Event()
        outcome = []

        def receive():
            try:
                receive_code("right", ready=ready.set, timeout=.3)
            except TimeoutError:
                outcome.append("deadline")

        worker = threading.Thread(target=receive)
        worker.start()
        self.assertTrue(ready.wait(2))
        with socket.create_connection(("127.0.0.1", PORT), timeout=1) as connection:
            connection.sendall(b"GET /?state=right&code=not-complete HTTP/1.1\r\nHost:")
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(outcome, ["deadline"])

    def test_installed_sdk_sends_pkce_and_keeps_refresh_token_in_memory(self):
        from google_auth_oauthlib.flow import InstalledAppFlow
        from shop_demo.google_consent import REDIRECT, SCOPE
        config = client_config(json.dumps({"installed": {"client_id": "test.apps.googleusercontent.com",
            "client_secret": "dummy", "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"}}))
        flow = InstalledAppFlow.from_client_config(config, [SCOPE], redirect_uri=REDIRECT,
            autogenerate_code_verifier=True)
        url, state = flow.authorization_url(prompt="consent", access_type="offline")
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["redirect_uri"], [REDIRECT])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["state"], [state])
        self.assertNotIn("client_secret", query)
        code = callback_code("/?state=" + state + "&code=synthetic", state)
        token = {"access_token": "synthetic", "refresh_token": "synthetic-refresh", "token_type": "Bearer",
                 "expires_at": 2000000000}
        with patch.object(flow.oauth2session, "fetch_token", return_value=token) as exchange:
            flow.fetch_token(code=code, timeout=30)
        self.assertEqual(exchange.call_args.kwargs["code_verifier"], flow.code_verifier)
        self.assertEqual(exchange.call_args.kwargs["code"], "synthetic")
        flow.oauth2session.token = token
        self.assertEqual(json.loads(flow.credentials.to_json())["refresh_token"], "synthetic-refresh")

    def test_callback_rejects_wrong_state_duplicate_code_and_remote_path(self):
        for path in ("/?state=wrong&code=abc", "/?state=right&code=a&code=b",
                     "http://example.test/?state=right&code=abc", "/?state=right&error=denied"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                callback_code(path, "right")
        self.assertEqual(callback_code("/?state=right&code=abc", "right"), "abc")

    def test_real_loopback_receiver_keeps_waiting_after_invalid_callback(self):
        ready = threading.Event()
        result = []
        worker = threading.Thread(target=lambda: result.append(receive_code("right", ready=ready.set, timeout=5)))
        worker.start()
        self.assertTrue(ready.wait(3))
        try:
            with self.assertRaises(HTTPError):
                urlopen(f"http://127.0.0.1:{PORT}/?state=wrong&code=abc", timeout=2)
            with urlopen(f"http://127.0.0.1:{PORT}/?state=right&code=abc", timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        finally:
            worker.join(6)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, ["abc"])

    def test_client_config_refuses_non_google_token_endpoint(self):
        raw = {"installed": {"client_id": "test.apps.googleusercontent.com", "client_secret": "dummy",
               "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://example.test/token"}}
        with self.assertRaises(ValueError):
            client_config(json.dumps(raw))


if __name__ == "__main__":
    unittest.main()
