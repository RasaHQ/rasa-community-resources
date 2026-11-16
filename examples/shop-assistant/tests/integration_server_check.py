"""Installed Google extra and host adapter, real SDK with synthetic responses."""
import importlib.metadata
import json
from pathlib import Path
import socket
import tomllib
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from pydantic import SecretStr
from shop_demo.google_runtime import google_service
from shop_demo.integration_tables import GoogleTables
from shop_demo.sheets import SheetFailure

PROJECT = Path(__file__).resolve().parent.parent
TOKEN = SecretStr(json.dumps({"client_id": "synthetic.apps.googleusercontent.com",
    "client_secret": "synthetic-client", "refresh_token": "synthetic-refresh",
    "token_uri": "https://oauth2.googleapis.com/token"}))


class InstalledSheetsTests(unittest.TestCase):
    def test_installed_google_extra_read_and_raw_append_through_real_sdk(self):
        from googleapiclient.http import HttpRequest
        configured = tomllib.loads((PROJECT / "server/pyproject.toml").read_text())["project"]["dependencies"]
        pin = next(value for value in configured if value.startswith("zeo-integrations[google] @")).rsplit("@", 1)[1]
        installed = json.loads(importlib.metadata.distribution("zeo-integrations").read_text("direct_url.json"))
        self.assertEqual(installed["vcs_info"]["commit_id"], pin)
        self.assertTrue(importlib.metadata.version("google-api-python-client"))
        calls = []

        def execute(request, *args, **kwargs):
            calls.append((request.methodId, request.uri, request.body))
            if request.methodId.endswith(".get"):
                return {"values": [["NOTEBOOK", "Notebook", "12900", "12"]]}
            return {"updates": {"updatedRows": 1}}

        with patch.object(socket.socket, "connect", side_effect=AssertionError("No provider network")), \
                patch("zeo_integrations.google.sheets.service.GoogleAuthProvider") as auth, \
                patch("google.auth.default", side_effect=AssertionError("No default credentials")), \
                patch.object(HttpRequest, "execute", execute):
            tables = GoogleTables(google_service(TOKEN), "synthetic-sheet")
            self.assertEqual(tables.read("Products"), [["NOTEBOOK", "Notebook", "12900", "12"]])
            tables.append("Orders", ["synthetic-order", "=literal", 12900, "MXN", "placed", "synthetic-date", "synthetic-request"])
        auth.assert_not_called()
        self.assertEqual(len(calls), 2)
        method, uri, body = calls[1]
        self.assertTrue(method.endswith(".append"))
        self.assertEqual(parse_qs(urlsplit(uri).query)["valueInputOption"], ["RAW"])
        self.assertEqual(json.loads(body)["values"][0][1], "=literal")

    def test_installed_provider_error_is_sanitized_and_not_retried(self):
        from googleapiclient.http import HttpRequest
        with patch.object(socket.socket, "connect", side_effect=AssertionError("No provider network")), \
                patch.object(HttpRequest, "execute", side_effect=RuntimeError("synthetic-private-error")) as execute:
            tables = GoogleTables(google_service(TOKEN), "synthetic-sheet")
            with self.assertRaises(SheetFailure) as caught:
                tables.read("Products")
        self.assertNotIn("synthetic-private-error", str(caught.exception))
        execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
