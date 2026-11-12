"""Raw protocol and real loopback controls; no SDK, bank or model call."""
import http.client
import json
import threading
import unittest

from server import MCP, local_server, MAX_REQUEST

EXPECTED = {"banking_accounts", "banking_balance", "banking_history",
            "banking_loan_payment", "banking_payoff", "banking_review_transfer",
            "banking_transfer_status"}


class Host:
    def __init__(self):
        self.calls = []
        self.failure = False

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        if self.failure:
            raise RuntimeError("private-vendor-body-and-credential")
        return {"fixture": "fictional", "available": True}


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.host = Host()
        self.server = MCP(self.host)

    def call(self, name, arguments=None):
        return self.server.handle(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}}}).encode())

    def test_exact_seven_no_identity_confirmation_or_dispatch_tools(self):
        result = self.server.handle(b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
        tools = result["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, EXPECTED)
        for tool in tools:
            self.assertFalse(tool["inputSchema"]["additionalProperties"])
            self.assertFalse(set(tool["inputSchema"]["properties"]) & {"principal", "session", "institution", "confirmed", "assured_at", "capability"})
        self.assertEqual(self.host.calls, [])

    def test_initialize_and_ping(self):
        reply = self.server.handle(b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}')
        self.assertEqual(reply["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(self.server.handle(b'{"jsonrpc":"2.0","id":1,"method":"ping"}')["result"], {})

    def test_supported_tool_calls_reach_host_once(self):
        cases = {"banking_accounts": {}, "banking_balance": {"account": "checking"},
            "banking_history": {"account": "checking", "start_date": "2026-01-01", "end_date": "2026-01-31"},
            "banking_loan_payment": {"loan": "car"}, "banking_payoff": {"loan": "car", "payoff_date": "2026-11-13"},
            "banking_review_transfer": {"source": "checking", "destination": "savings", "amount": "1.25"},
            "banking_transfer_status": {}}
        for name, args in cases.items():
            self.assertFalse(self.call(name, args)["result"]["isError"])
        self.assertEqual(len(self.host.calls), 7)

    def test_private_methods_unknown_names_and_extra_identity_refuse_before_host(self):
        for name in ("submit_transfer", "banking_submit_transfer", "reset", "confirm", "session", "missing"):
            self.assertEqual(self.call(name)["error"]["code"], -32602)
        self.assertEqual(self.call("banking_accounts", {"principal": "other"})["error"]["code"], -32602)
        self.assertEqual(self.host.calls, [])

    def test_raw_types_dates_amounts_and_fields_never_coerce(self):
        cases = [("banking_balance", {"account": 1}), ("banking_balance", {"account": True}),
            ("banking_balance", {"account": "../private"}), ("banking_balance", {}),
            ("banking_payoff", {"loan": "car", "payoff_date": "2026-02-30"}),
            ("banking_payoff", {"loan": "car", "payoff_date": "20261113"}),
            ("banking_history", {"account": "checking", "start_date": "2026-02-01", "end_date": "2026-01-01"}),
            ("banking_review_transfer", {"source": "checking", "destination": "savings", "amount": 1.25}),
            ("banking_review_transfer", {"source": "checking", "destination": "savings", "amount": "01.25"}),
            ("banking_review_transfer", {"source": "checking", "destination": "checking", "amount": "1.00"})]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments):
                self.assertEqual(self.call(name, arguments)["error"]["code"], -32602)
        self.assertEqual(self.host.calls, [])

    def test_duplicate_nonfinite_invalid_json_and_oversize_refuse(self):
        for raw in (b'{"jsonrpc":"2.0","id":1,"id":2}', b'{"id":NaN}', b'\xff', b'x'*(MAX_REQUEST+1)):
            self.assertEqual(self.server.handle(raw)["error"]["code"], -32700)
        self.assertEqual(self.host.calls, [])

    def test_utf16_body_and_null_id_cannot_reach_host(self):
        body = '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"banking_accounts"}}'
        self.assertEqual(self.server.handle(body.encode("utf-16"))["error"]["code"], -32700)
        self.assertEqual(self.server.handle(body.replace('"id":1', '"id":null').encode())["error"]["code"], -32600)
        self.assertEqual(self.host.calls, [])

    def test_tool_notifications_cannot_dispatch(self):
        result = self.server.handle(b'{"jsonrpc":"2.0","method":"tools/call","params":{"name":"banking_accounts"}}')
        self.assertIn("error", result)
        self.assertIsNone(self.server.handle(b'{"jsonrpc":"2.0","method":"notifications/initialized"}'))
        self.assertEqual(self.host.calls, [])

    def test_execution_errors_never_return_raw_diagnostic(self):
        self.host.failure = True
        reply = self.call("banking_accounts")
        self.assertTrue(reply["result"]["isError"])
        self.assertNotIn("private-vendor", json.dumps(reply))

    def test_schema_result_mutation_cannot_change_validation(self):
        reply = self.server.handle(b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
        reply["result"]["tools"][1]["inputSchema"]["properties"].clear()
        self.assertIn("error", self.call("banking_balance"))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.host = Host()
        self.bearer = "fictional-test-capability-1234567890"
        self.server = local_server(self.host, self.bearer)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.thread.join(2)
        self.server.server_close()
        self.assertFalse(self.thread.is_alive())

    def request(self, method="POST", path="/mcp", body=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}', headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            fields = {"Authorization": "Bearer " + self.bearer, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
            fields.update(headers or {})
            connection.request(method, path, body, fields)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_real_loopback_discovery(self):
        status, body = self.request()
        self.assertEqual(status, 200)
        self.assertEqual({tool["name"] for tool in json.loads(body)["result"]["tools"]}, EXPECTED)
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_auth_origin_host_and_path_checked_before_tools(self):
        for headers in ({"Authorization": "wrong"}, {"Origin": "https://evil.invalid"}, {"Host": "evil.invalid"}):
            with self.subTest(headers=headers):
                self.assertIn(self.request(headers=headers)[0], {401,403})
        self.assertEqual(self.request(path="/confirm")[0], 403)
        self.assertEqual(self.host.calls, [])

    def test_accepted_notification_has_no_response_body(self):
        self.assertEqual(self.request(body=b'{"jsonrpc":"2.0","method":"notifications/initialized"}'), (202,b""))

    def test_get_delete_media_and_oversize(self):
        self.assertEqual(self.request(method="GET")[0], 405)
        self.assertEqual(self.request(method="DELETE")[0], 405)
        self.assertEqual(self.request(headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request(body=b'x'*(MAX_REQUEST+1))[0], 400)
        self.assertEqual(self.request(headers={"Content-Length": "+58"})[0], 400)
        self.assertEqual(self.host.calls, [])


if __name__ == "__main__":
    unittest.main()
