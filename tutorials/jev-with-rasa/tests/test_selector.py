"""The real SDK serialises requests and decodes scripted HTTP responses."""
import json
import unittest
import httpx2
from typesafe_sdk import RetryPolicy, TypeSafeClient
from jacaranda_jev.accounts import Accounts
from jacaranda_jev.scripted import scripted_transport
from jacaranda_jev.selector import MODEL, Selector


class SelectionControls(unittest.TestCase):
    def setUp(self):
        self.accounts = Accounts()
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()

    def selector(self, transport):
        client = TypeSafeClient(api_key="scripted-local-test", base_url="https://scripted.invalid",
                               transport=transport, retry=RetryPolicy(max_retries=0), model=MODEL)
        self.clients.append(client)
        return Selector(client, self.accounts)

    def altered(self, change):
        transport, requests = scripted_transport()
        def reply(request):
            response = transport.handle_request(request)
            body = json.loads(response.content)
            change(body)
            return httpx2.Response(200, json=body)
        return self.selector(httpx2.MockTransport(reply)), requests

    def test_current_account_read(self):
        transport, calls = scripted_transport()
        result = self.selector(transport).select("demo-a", "Show my current account")
        self.assertEqual(result["status"], "transactions")
        self.assertEqual(self.accounts.reads, ["A-CURRENT"])
        self.assertEqual(len(calls), 1)
        self.assertIsNone(result["decision"]["input_tokens"])

    def test_request_contains_only_offered_owner_accounts_and_model_pin(self):
        transport, calls = scripted_transport()
        self.selector(transport).select("demo-a", "My account")
        self.assertEqual(set(calls[0]["questions"]["account"]["criteria"]),
                         {"A-CURRENT", "A-SAVINGS", "ask_customer"})
        self.assertEqual(calls[0]["model"], MODEL)
        self.assertEqual(calls[0]["state"], {"customer_message": "My account"})

    def test_high_confidence_cannot_authorise_a_stale_choice(self):
        transport, _ = scripted_transport(before_reply=lambda: self.accounts.retire("A-CURRENT"))
        result = self.selector(transport).select("demo-a", "Current account")
        self.assertEqual(result["decision"]["confidence"], 1.0)
        self.assertEqual(result["status"], "stale_options")
        self.assertEqual(self.accounts.reads, [])

    def test_high_confidence_cannot_add_another_owners_account(self):
        selector, _ = self.altered(lambda b: b["answers"]["account"].update(choice="B-CURRENT"))
        self.assertEqual(selector.select("demo-a", "Current")["status"], "invalid_decision")
        self.assertEqual(self.accounts.reads, [])

    def test_clarification_does_not_read(self):
        transport, _ = scripted_transport("ask_customer")
        result = self.selector(transport).select("demo-a", "My account")
        self.assertEqual(result["status"], "needs_account")
        self.assertEqual(result["options"], ["current account", "savings account"])
        self.assertEqual(self.accounts.reads, [])

    def test_unknown_demo_does_not_call_sdk(self):
        transport, calls = scripted_transport()
        self.assertEqual(self.selector(transport).select("missing", "My account"), {"status": "unknown_demo"})
        self.assertEqual(calls, [])

    def test_invalid_message_does_not_call_sdk(self):
        transport, calls = scripted_transport()
        selector = self.selector(transport)
        for message in (None, " ", "x" * 2001):
            self.assertEqual(selector.select("demo-a", message), {"status": "invalid_message"})
        self.assertEqual(calls, [])

    def test_no_accounts_does_not_call_sdk(self):
        self.accounts.retire("A-CURRENT")
        self.accounts.retire("A-SAVINGS")
        transport, calls = scripted_transport()
        self.assertEqual(self.selector(transport).select("demo-a", "Account"), {"status": "no_accounts"})
        self.assertEqual(calls, [])

    def test_model_drift_is_refused(self):
        selector, _ = self.altered(lambda b: b.update(model="jev-next"))
        self.assertEqual(selector.select("demo-a", "Current")["status"], "invalid_decision")

    def test_missing_answer_is_refused(self):
        selector, _ = self.altered(lambda b: b.update(answers={}))
        self.assertEqual(selector.select("demo-a", "Current")["status"], "invalid_decision")

    def test_probability_keys_must_match_the_request(self):
        selector, _ = self.altered(lambda b: b["answers"]["account"]["probabilities"].update(extra=0.0))
        self.assertEqual(selector.select("demo-a", "Current")["status"], "invalid_decision")

    def test_invalid_confidence_is_refused(self):
        selector, _ = self.altered(lambda b: b["answers"]["account"].update(confidence=1.1))
        self.assertEqual(selector.select("demo-a", "Current")["status"], "invalid_decision")

    def test_invalid_probability_sum_is_refused(self):
        selector, _ = self.altered(lambda b: b["answers"]["account"]["probabilities"].update(**{"A-SAVINGS": 0.5}))
        self.assertEqual(selector.select("demo-a", "Current")["status"], "invalid_decision")

    def test_retryable_http_error_makes_only_one_attempt(self):
        calls = []
        def reply(request):
            calls.append(request)
            return httpx2.Response(503, json={"error": "scripted unavailable"})
        result = self.selector(httpx2.MockTransport(reply)).select("demo-a", "Current")
        self.assertEqual(result, {"status": "decision_unavailable"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.accounts.reads, [])

    def test_one_client_is_reused_for_two_requests(self):
        transport, calls = scripted_transport()
        selector = self.selector(transport)
        selector.select("demo-a", "Current")
        selector.select("demo-a", "Current again")
        self.assertEqual(len(self.clients), 1)
        self.assertEqual(len(calls), 2)

    def test_execution_guard_alone_refuses_unknown_choice(self):
        self.assertEqual(self.accounts.read(self.accounts.snapshot("demo-a"), "B-CURRENT"),
                         {"status": "choice_not_offered"})

    def test_sdk_type_decoding_does_not_enforce_offered_choice_membership(self):
        from jacaranda_jev.selector import question
        selector, _ = self.altered(lambda b: b["answers"]["account"].update(choice="B-CURRENT"))
        q = question(self.accounts.snapshot("demo-a"))
        response = selector.client.system_one(model=MODEL, state="Current", questions={"account": q})
        self.assertEqual(response.choices["account"].choice, "B-CURRENT")
        self.assertNotIn(response.choices["account"].choice, q.criteria)

    def test_valid_eligible_choice_can_still_be_wrong_for_the_request(self):
        transport, _ = scripted_transport("A-SAVINGS")
        result = self.selector(transport).select("demo-a", "Show my current account")
        self.assertEqual(result["status"], "transactions")
        self.assertEqual(result["account"], "A-SAVINGS")
        self.assertEqual(result["decision"]["confidence"], 1.0)
        # This fixture passes wire/permission checks and deliberately fails the
        # user's requested account. Selection quality is a separate check.

    def test_active_state_is_rechecked_even_if_revision_was_not_bumped(self):
        snapshot = self.accounts.snapshot("demo-a")
        self.accounts.records["A-CURRENT"] = ("demo-a", "current account", False)
        self.assertEqual(self.accounts.read(snapshot, "A-CURRENT"), {"status": "account_unavailable"})
        self.assertEqual(self.accounts.reads, [])

    def test_owner_is_rechecked_even_if_revision_was_not_bumped(self):
        snapshot = self.accounts.snapshot("demo-a")
        self.accounts.records["A-CURRENT"] = ("demo-b", "current account", True)
        self.assertEqual(self.accounts.read(snapshot, "A-CURRENT"), {"status": "account_unavailable"})
        self.assertEqual(self.accounts.reads, [])

    def test_non_json_response_is_unavailable(self):
        calls = []
        def reply(request):
            calls.append(request)
            return httpx2.Response(200, text="not JSON")
        result = self.selector(httpx2.MockTransport(reply)).select("demo-a", "Current")
        self.assertEqual(result, {"status": "decision_unavailable"})
        self.assertEqual(len(calls), 1)

    def test_malformed_answer_is_unavailable(self):
        selector, calls = self.altered(lambda b: b["answers"]["account"].update(confidence="not a number"))
        self.assertEqual(selector.select("demo-a", "Current"), {"status": "decision_unavailable"})
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
