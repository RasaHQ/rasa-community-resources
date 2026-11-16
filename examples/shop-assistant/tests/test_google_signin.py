import contextlib
import io
import json
import os
from pathlib import Path
import socket
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch

from google_auth_oauthlib.flow import InstalledAppFlow
from shop_demo.google_signin import REDIRECT, SCOPE, callback_code, client_config, main

CLIENT = {"installed": {"client_id": "test.apps.googleusercontent.com",
    "client_secret": "synthetic-client-secret", "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"}}


class SignInTests(unittest.TestCase):
    def test_callback_requires_exact_redirect_state_and_one_nonempty_code(self):
        valid = REDIRECT + "?state=right&code=synthetic"
        self.assertEqual(callback_code(valid, "right"), "synthetic")
        for address in (
            valid.replace("http:", "https:"), valid.replace("127.0.0.1", "localhost"),
            valid.replace(":8766", ":8767"), valid.replace("127.0.0.1", "127.0.0.1.evil.test"),
            valid.replace("127.0.0.1", "user@127.0.0.1"), valid.replace("/?", "/other?"),
            valid + "#fragment", "/?state=right&code=synthetic", valid + "&state=right",
            valid.replace("state=right", "state=wrong"), valid + "&code=second",
            valid.replace("code=synthetic", "code="), valid.replace("code=synthetic", "code=%20"),
            valid + "&error=denied", valid + "&error_description=denied",
            valid.replace("127.0.0.1", "127.0.0.1\n"),
        ):
            with self.subTest(address=address), self.assertRaises(ValueError):
                callback_code(address, "right")

    def test_config_requires_desktop_client_and_google_endpoints(self):
        self.assertEqual(client_config(json.dumps(CLIENT)), CLIENT)
        invalid = [{"web": CLIENT["installed"]}, {"installed": []}]
        for field, value in (("auth_uri", "https://example.test/authorize"),
                ("token_uri", "https://example.test/token"), ("client_id", "not-google"),
                ("client_secret", ""), ("client_id", 123)):
            invalid.append({"installed": {**CLIENT["installed"], field: value}})
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                client_config(json.dumps(value))

    def run_signin(self, *, address=None, refresh=True, exchange_error=False):
        flow = InstalledAppFlow.from_client_config(CLIENT, [SCOPE], redirect_uri=REDIRECT,
            autogenerate_code_verifier=True)
        token = {"access_token": "synthetic-access", "token_type": "Bearer", "expires_at": 2000000000}
        if refresh:
            token["refresh_token"] = "synthetic-refresh"
        output, errors = io.StringIO(), io.StringIO()
        observed = {}
        original_url = flow.authorization_url

        def authorization_url(**kwargs):
            url, state = original_url(**kwargs)
            observed.update(query=parse_qs(urlsplit(url).query), state=state)
            return url, state

        def pasted(_):
            if address is not None:
                return address
            return REDIRECT + "?" + urlencode({"state": observed["state"], "code": "synthetic-code"})

        def exchange(*args, **kwargs):
            if exchange_error:
                raise RuntimeError("synthetic-client-secret synthetic-code synthetic-access")
            flow.oauth2session.token = token
            return token

        # Actual locked SDK URL construction and PKCE, synthetic exchange only.
        # A file write or socket creation would fail this control.
        with patch.dict(os.environ, {"GOOGLE_CLIENT_SECRETS_JSON": json.dumps(CLIENT)}, clear=True), \
                patch.object(InstalledAppFlow, "from_client_config", return_value=flow) as factory, \
                patch.object(flow, "authorization_url", side_effect=authorization_url), \
                patch.object(flow.oauth2session, "fetch_token", side_effect=exchange) as fetch, \
                patch("builtins.input", side_effect=pasted), \
                patch("builtins.open", side_effect=AssertionError("No file access")), \
                patch.object(Path, "write_text", side_effect=AssertionError("No file write")), \
                patch.object(Path, "write_bytes", side_effect=AssertionError("No file write")), \
                patch.object(socket, "socket", side_effect=AssertionError("No network/listener")), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main()
        return result, output.getvalue(), errors.getvalue(), observed, flow, factory, fetch

    def test_installed_sdk_uses_pkce_and_prints_one_authorized_user_token(self):
        result, out, err, observed, flow, factory, fetch = self.run_signin()
        self.assertEqual(result, 0, err)
        self.assertEqual(factory.call_args.args[1], [SCOPE])
        self.assertEqual(factory.call_args.kwargs["redirect_uri"], REDIRECT)
        self.assertTrue(factory.call_args.kwargs["autogenerate_code_verifier"])
        query = observed["query"]
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["redirect_uri"], [REDIRECT])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent"])
        self.assertEqual(query["scope"], [SCOPE])
        self.assertNotIn("client_secret", query)
        self.assertEqual(fetch.call_args.kwargs["code_verifier"], flow.code_verifier)
        self.assertEqual(fetch.call_args.kwargs["code"], "synthetic-code")
        self.assertEqual(fetch.call_args.kwargs["timeout"], 30)
        tokens = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0]["refresh_token"], "synthetic-refresh")
        self.assertEqual(err, "")

    def test_rejected_callback_never_reaches_exchange(self):
        result, out, err, _, _, _, fetch = self.run_signin(
            address=REDIRECT + "?state=wrong&code=synthetic-code")
        self.assertEqual(result, 1)
        fetch.assert_not_called()
        self.assertFalse(any(line.startswith("{") for line in out.splitlines()))
        self.assertNotIn("synthetic-code", err)

    def test_missing_refresh_token_and_exchange_failure_never_print_token(self):
        for options in ({"refresh": False}, {"exchange_error": True}):
            with self.subTest(options=options):
                result, out, err, *_ = self.run_signin(**options)
                self.assertEqual(result, 1)
                self.assertFalse(any(line.startswith("{") for line in out.splitlines()))
                for sensitive in ("synthetic-client-secret", "synthetic-code", "synthetic-access"):
                    self.assertNotIn(sensitive, err)

    def test_missing_or_malformed_client_errors_hide_input(self):
        for environment in ({}, {"GOOGLE_CLIENT_SECRETS_JSON": "synthetic-private-invalid"}):
            with patch.dict(os.environ, environment, clear=True), \
                    contextlib.redirect_stdout(io.StringIO()) as out, \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(), 1)
                self.assertEqual(out.getvalue(), "")
                self.assertNotIn("synthetic-private-invalid", err.getvalue())


if __name__ == "__main__":
    unittest.main()
