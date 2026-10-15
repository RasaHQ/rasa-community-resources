"""Exercise Agno's actual OpenAI client against an in-memory HTTP transport.

No model provider, credential, socket or fabricated model-performance result.
The two responses are explicit client-contract fixtures, not captured inference.
"""
import json
import tempfile
import unittest
from pathlib import Path

import httpx
from agno.models.openai import OpenAIChat
from shop_adviser.service import AdviserService


class OpenAIClientContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.requests = []

    def completion(self, message, finish_reason):
        return {
            "id": "offline-fixture-completion",
            "object": "chat.completion",
            "created": 1,
            "model": "offline-fixture",
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def service(self, *, provider_error=False):
        def handle(request):
            self.assertEqual(request.url.host, "provider.invalid")
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertEqual(request.method, "POST")
            body = json.loads(request.content)
            self.requests.append(body)
            if provider_error:
                return httpx.Response(503, json={"error": {"message": "fixture_unavailable", "type": "server_error"}})
            if len(self.requests) == 1:
                self.assertIn("lookup_product", [tool["function"]["name"] for tool in body["tools"]])
                self.assertEqual(body["response_format"]["type"], "json_schema")
                return httpx.Response(200, json=self.completion({
                    "role": "assistant", "content": None,
                    "tool_calls": [{"id": "offline-product", "type": "function", "function": {"name": "lookup_product", "arguments": "{}"}}],
                }, "tool_calls"))
            self.assertEqual(len(self.requests), 2, "Unexpected additional client call")
            tools = [m for m in body["messages"] if m["role"] == "tool"]
            self.assertTrue(any("WS-HAND-01" in str(m["content"]) for m in tools))
            return httpx.Response(200, json=self.completion({
                "role": "assistant", "content": json.dumps({"product_id": "WS-HAND-01", "explanation": "Scripted client-contract response."}),
            }, "stop"))

        client = httpx.Client(transport=httpx.MockTransport(handle), trust_env=False)
        self.addCleanup(client.close)
        model = OpenAIChat(id="offline-fixture", api_key="not-a-real-provider-key",
                           base_url="https://provider.invalid/v1", http_client=client,
                           max_retries=0)
        return AdviserService(Path(self.tmp.name) / "shop.sqlite", lambda: model)

    def test_native_client_serializes_tool_call_and_reads_structured_reply(self):
        result = self.service().answer("willow-a-chat", "Tell me about the public hand cream.")
        self.assertEqual(result, {"status": "ready", "product_id": "WS-HAND-01", "explanation": "Scripted client-contract response."})
        self.assertEqual(len(self.requests), 2)

    def test_native_client_error_is_unavailable_without_exposing_provider_message(self):
        result = self.service(provider_error=True).answer("willow-a-chat", "Product question")
        self.assertEqual(result, {"status": "advice_unavailable"})
        self.assertEqual(len(self.requests), 1)

    def test_unknown_sender_never_reaches_the_client(self):
        result = self.service().answer("unknown-demo-sender", "Product question")
        self.assertEqual(result, {"status": "unknown_demo_sender"})
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
