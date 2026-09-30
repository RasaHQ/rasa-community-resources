"""Offline checks for the Northgate transfer guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
(The hook tests need rasa and are skipped under a bare python3; `make proof-full`
runs them in the project venv.)
"""

from __future__ import annotations

import ast
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import ledger as nb  # noqa: E402

CASEBOOK_CONTRACT = PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "banking-transfer.json"
ELENA = "NB-CUST-4810"
JORDAN = "NB-CUST-5520"


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order. This contract has request rules only."""
    reason = nb.evaluate(facts, contract)
    return ("blocked", reason) if reason else ("succeeded", "verified_fixture_receipt")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), nb.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = nb.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))

    def test_all_three_rules_are_request_rules(self):
        self.assertEqual([r["field"] for r in nb.request_rules()],
                         ["ledger_revision_current", "payee_identity_confirmed", "funds_reserved"])


class Flow:
    """select_payee -> prepare_transfer -> submit_transfer, keeping memory the way the tools do."""

    def __init__(self, conversation: str = "c1", customer: str = ELENA) -> None:
        self.ledger = nb.Ledger()
        self.conv = conversation
        self.customer = customer
        self.selected = None
        self.draft = None

    def select(self, words):
        result = nb.select_payee(self.ledger, self.customer, words)
        self.selected = result.get("payee_ref")
        self.draft = None
        return result

    def prepare(self, source, amount, payee_ref=None):
        result = nb.prepare_transfer(self.ledger, self.customer, self.selected, source,
                                     payee_ref or self.selected, amount, self.conv)
        self.draft = result.get("draft_id")
        return result

    def submit(self, draft_id=None):
        result = nb.submit_transfer(self.ledger, self.customer, self.selected, self.draft,
                                    draft_id or self.draft, self.conv)
        if result["status"] == "blocked":
            self.draft = None
        return result

    def send(self, words, source, amount):
        self.select(words)
        self.prepare(source, amount)
        return self.submit()


class PayeeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.ledger = nb.Ledger()

    def select(self, words, customer=ELENA):
        return nb.select_payee(self.ledger, customer, words)

    def test_name_nickname_ending_and_own_account_resolve(self):
        self.assertEqual(self.select("Sam Patel")["payee_ref"], "NB-PAY-2042")
        self.assertEqual(self.select("the one ending 17")["payee_ref"], "NB-PAY-2017")
        self.assertEqual(self.select("my rent")["payee_ref"], "NB-PAY-2088")
        self.assertEqual(self.select("my savings")["payee_ref"], "NB-ACC-1003")
        self.assertEqual(self.select("Sam, ending 42")["payee_ref"], "NB-PAY-2042")

    def test_a_first_name_shared_by_two_payees_selects_neither(self):
        got = self.select("Sam")
        self.assertEqual((got["status"], got["reason"], got["detail"]), ("blocked", "unconfirmed_payee", "ambiguous"))
        self.assertEqual(len(got["candidates"]), 2)

    def test_name_and_ending_that_disagree_select_neither(self):
        got = self.select("Sam Patel ending 17")
        self.assertEqual((got["reason"], got["detail"]), ("unconfirmed_payee", "name_and_ending_disagree"))

    def test_unsaved_payee_and_another_customers_payee_look_the_same(self):
        unsaved = self.select("Jordan Blake, routing 021000089, account 55123455")
        others = self.select("Dana Blake")
        by_ref = self.select("NB-PAY-3001")
        for got in (unsaved, others, by_ref):
            self.assertEqual((got["status"], got["detail"]), ("blocked", "not_a_saved_payee"))
        self.assertEqual(others, by_ref)

    def test_accounts_resolve_and_plain_checking_is_ambiguous(self):
        self.assertEqual(nb.resolve_account(self.ledger, ELENA, "bills")["account_ref"], "NB-ACC-1002")
        self.assertEqual(nb.resolve_account(self.ledger, ELENA, "3301")["account_ref"], "NB-ACC-1001")
        self.assertEqual(nb.resolve_account(self.ledger, ELENA, "checking")["detail"], "ambiguous")
        self.assertEqual(nb.resolve_account(self.ledger, ELENA, "Jordan's everyday")["account_ref"], "NB-ACC-1001")
        self.assertEqual(nb.resolve_account(self.ledger, JORDAN, "everyday")["account_ref"], "NB-ACC-2001")


class SubmissionTests(unittest.TestCase):
    def test_saved_payee_transfer_is_pending_not_posted(self):
        flow = Flow()
        got = flow.send("Sam Patel", "everyday checking", "$75")
        self.assertEqual((got["status"], got["ledger_status"], got["posted"], got["effects"]),
                         ("submitted", "pending", False, 1))
        self.assertTrue(got["reference"].startswith("NB-TRF-"))
        self.assertIsNone(got["posted_at"])
        self.assertEqual(got["facts"], {"ledger_revision_current": True, "payee_identity_confirmed": True,
                                        "funds_reserved": True})
        # The reservation is a hold: available drops, posted does not.
        snap = flow.ledger.snapshot("NB-ACC-1001")
        self.assertEqual((snap["posted_balance"], snap["available_balance"]), ("$2,480.00", "$1,175.00"))

    def test_own_account_transfer_posts(self):
        flow = Flow()
        got = flow.send("my everyday checking", "savings", "300")
        self.assertEqual((got["status"], got["ledger_status"], got["posted"]), ("submitted", "posted", True))
        self.assertEqual(flow.ledger.snapshot("NB-ACC-1003")["posted_balance"], "$5,900.00")
        self.assertEqual(flow.ledger.snapshot("NB-ACC-1001")["posted_balance"], "$2,780.00")

    def test_a_debit_after_the_read_makes_the_draft_stale(self):
        flow = Flow()
        flow.select("savings")
        drafted = flow.prepare("bills", "400")
        self.assertEqual(drafted["balance_as_read"]["available_balance"], "$520.00")
        got = flow.submit()
        self.assertEqual((got["status"], got["reason"], got["effects"]), ("blocked", "stale_balance", 0))
        self.assertEqual(got["current"], {"available_balance": "$340.00", "posted_balance": "$340.00",
                                          "ledger_revision": 18})
        # Re-read: the same 400 cannot be reserved from what is left.
        flow.prepare("bills", "400")
        self.assertEqual(flow.submit()["reason"], "funds_not_reserved")
        # A smaller amount against the current revision goes through.
        flow.prepare("bills", "300")
        got = flow.submit()
        self.assertEqual((got["status"], got["ledger_status"], got["balance_revision"]), ("submitted", "posted", 18))

    def test_funds_are_decided_from_the_available_balance_at_submission(self):
        flow = Flow()
        drafted = flow.select("Sam Patel") and flow.prepare("everyday", "1,500")
        self.assertEqual(drafted["balance_as_read"]["posted_balance"], "$2,480.00")
        got = flow.submit()
        self.assertEqual((got["status"], got["reason"], got["effects"]), ("blocked", "funds_not_reserved", 0))
        self.assertIs(got["facts"]["funds_reserved"], False)
        self.assertEqual(flow.ledger.transfers.keys(), nb.Ledger().transfers.keys())

    def test_changing_the_payee_voids_the_confirmed_draft(self):
        flow = Flow()
        flow.select("Sam Patel")
        flow.prepare("everyday", "60")
        old_draft = flow.draft
        flow.select("Sam Okoro")
        # The old draft is no longer current, whatever the caller said about it.
        got = nb.submit_transfer(flow.ledger, ELENA, flow.selected, old_draft, old_draft, flow.conv)
        self.assertEqual((got["status"], got["reason"]), ("blocked", "unconfirmed_payee"))
        self.assertIs(got["facts"]["payee_identity_confirmed"], False)
        self.assertEqual(flow.submit(old_draft)["reason"], "draft_superseded")
        flow.prepare("everyday", "60")
        self.assertEqual(flow.submit()["destination"],
                         "Sam Okoro, saved payee at Crestline Bank, account ending 17")

    def test_a_payee_ref_that_was_not_selected_is_refused(self):
        flow = Flow()
        flow.select("Sam Patel")
        for ref in ("NB-PAY-2017", "NB-PAY-3001", "NB-PAY-9999"):
            got = flow.prepare("everyday", "10", payee_ref=ref)
            self.assertEqual((got["reason"], got["detail"]), ("unconfirmed_payee", "not_the_selected_payee"))

    def test_resubmitting_a_draft_is_a_replay(self):
        flow = Flow()
        first = flow.send("Sam Okoro", "everyday", "40")
        again = flow.submit(first["attempt_id"])
        self.assertEqual((again["replay"], again["effects"], again["reference"]), (True, 0, first["reference"]))
        self.assertEqual(sum(1 for t in flow.ledger.transfers.values() if t.get("attempt_id")), 1)

    def test_bad_amounts_are_refused(self):
        flow = Flow()
        flow.select("Sam Okoro")
        for amount in ("-5", "0", "ten", "10.005", ""):
            self.assertEqual(flow.prepare("everyday", amount)["reason"], "invalid_amount", amount)


class RecoveryTests(unittest.TestCase):
    def test_lost_acknowledgement_is_found_by_attempt_id_and_never_resent(self):
        flow = Flow()
        got = flow.send("my rent", "everyday", "950")
        self.assertEqual((got["status"], got["reason"], got["reference"], got["effects"]),
                         ("unconfirmed", "acknowledgment_lost", None, 1))
        found = nb.check_transfer_status(flow.ledger, ELENA, got["attempt_id"])
        self.assertEqual((found["status"], found["ledger_status"]), ("read", "pending"))
        self.assertTrue(found["reference"].startswith("NB-TRF-"))
        flow.select("Kestrel Lettings")
        again = flow.prepare("everyday", "950")
        self.assertEqual((again["status"], again["reason"], again["prior_attempt_id"]),
                         ("blocked", "prior_attempt_unresolved", got["attempt_id"]))
        self.assertEqual(sum(1 for t in flow.ledger.transfers.values() if t.get("attempt_id")), 1)

    def test_unknown_scheme_state_stays_unknown_and_escalates(self):
        flow = Flow()
        got = flow.send("Priya", "everyday", "120")
        self.assertEqual((got["status"], got["reason"], got["ledger_status"]),
                         ("unconfirmed", "scheme_response_unknown", "unknown"))
        self.assertEqual(nb.check_transfer_status(flow.ledger, ELENA, got["reference"])["ledger_status"], "unknown")
        escalated = nb.escalate_reconciliation(flow.ledger, ELENA, got["reference"], "no scheme state")
        self.assertEqual((escalated["status"], escalated["owner"]), ("escalated", "payments ledger owner"))

    def test_existing_transfers_and_other_customers_references(self):
        led = nb.Ledger()
        self.assertEqual(nb.check_transfer_status(led, ELENA, "NB-TRF-7731")["ledger_status"], "pending")
        self.assertEqual(nb.check_transfer_status(led, ELENA, "nb-trf-7702")["ledger_status"], "posted")
        self.assertEqual(nb.check_transfer_status(led, ELENA, "NB-TRF-7790")["status"], "not_found")
        self.assertEqual(nb.check_transfer_status(led, ELENA, "NB-TRF-0000")["status"], "not_found")
        self.assertEqual(nb.escalate_reconciliation(led, ELENA, "NB-TRF-7702", "x")["status"], "not_needed")

    def test_conversations_do_not_share_a_ledger(self):
        nb.ledger_for("a").accounts["NB-ACC-1001"]["revision"] += 5
        self.assertEqual(nb.ledger_for("b").accounts["NB-ACC-1001"]["revision"], 41)


class WordingTests(unittest.TestCase):
    def test_posted_claims_are_caught(self):
        for text in (
            "Your transfer has gone through.",
            "Done. The transfer is complete.",
            "The $75 has been sent and has posted to Sam's account.",
            "I've sent $75 to Sam Patel.",
            "It went through, reference NB-TRF-1234.",
            "Sam has it now.",
            "The money is in his account.",
        ):
            with self.subTest(text=text):
                self.assertTrue(nb.posted_claims(text), text)

    def test_pending_and_hedged_language_passes(self):
        for text in (
            "The transfer is submitted and pending, reference NB-TRF-1234.",
            "It has not posted yet.",
            "Once it has posted, Sam will see it.",
            "It isn't complete until the payee's bank receives it.",
            "I've sent a request to the ledger; it is pending.",
            "Has it gone through?",
            "Nothing was submitted.",
        ):
            with self.subTest(text=text):
                self.assertEqual(nb.posted_claims(text), [], text)

    def test_case_build_metric_uses_the_same_patterns(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metric = spec["bot_text_metrics"]["posted_claim"]
        self.assertEqual(metric["pattern"], nb.POSTED_CLAIM_RE.pattern)
        self.assertEqual(metric["unless_before"], nb.POSTED_HEDGE_RE.pattern)
        re.compile(metric["pattern"])


class ToolSurfaceTests(unittest.TestCase):
    """No tool lets the model assert a fact, a balance or a payee account number."""

    def params(self, path: Path) -> dict[str, list[str]]:
        tree = ast.parse(path.read_text())
        return {n.name: [a.arg for a in n.args.args] for n in tree.body if isinstance(n, ast.AsyncFunctionDef)}

    def test_tool_parameters(self):
        skill = self.params(PROJECT / "skills" / "transfer_money" / "tools.py")
        shared = self.params(PROJECT / "tools" / "northgate_shared.py")
        self.assertEqual(set(skill), {"select_payee", "prepare_transfer", "submit_transfer"})
        self.assertEqual(set(shared), {"load_caller_profile", "get_balance", "check_transfer_status",
                                       "escalate_reconciliation"})
        for name, args in {**skill, **shared}.items():
            for arg in args:
                self.assertNotRegex(arg, r"balance|revision|confirmed|reserved|routing|account_number|customer|posted",
                                    f"{name}({arg})")


class OutputHookTests(unittest.TestCase):
    """hooks.py against the installed engine's payload types (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            import hooks  # noqa: F401
            from rasa.mantle.hooks import ModelResponsePayload, RetryModel, ToolResultPayload
        except ImportError as exc:  # bare python3 without the project venv
            raise unittest.SkipTest(f"rasa not importable: {exc}")
        cls.hooks, cls.Model, cls.Retry, cls.Tool = hooks, ModelResponsePayload, RetryModel, ToolResultPayload

    def run_hook(self, coro):
        import asyncio

        return asyncio.run(coro)

    def respond(self, sender, text):
        return self.run_hook(self.hooks.block_posted_claims(self.Model(sender_id=sender, text=text)))

    def tool(self, sender, name, result):
        # The engine passes the result as serialized JSON text, as dispatched.
        self.run_hook(self.hooks.remember_ledger_states(
            self.Tool(sender_id=sender, tool_name=name, arguments={}, value=json.dumps(result))))

    def test_pending_transfer_claimed_as_sent_retries_then_states_the_ledger(self):
        sender = "pending"
        got = Flow(sender).send("Sam Patel", "everyday", "75")
        self.tool(sender, "submit_transfer", got)
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(self.Retry) as raised:
                self.respond(sender, "All done, the $75 has gone through to Sam.")
            self.assertIn("ledger_status pending", raised.exception.feedback)
        replaced = self.respond(sender, "It went through.")
        self.assertIn(got["reference"], replaced.text)
        self.assertIn("pending", replaced.text)

    def test_posted_own_transfer_may_be_called_posted(self):
        sender = "posted"
        self.tool(sender, "submit_transfer", Flow(sender).send("my everyday checking", "savings", "300"))
        text = "Done: $300 has been transferred and is posted."
        self.assertEqual(self.respond(sender, text).text, text)

    def test_lost_ack_then_lookup_replaces_the_attempt(self):
        sender = "acklost"
        flow = Flow(sender)
        got = flow.send("my rent", "everyday", "950")
        self.tool(sender, "submit_transfer", got)
        found = nb.check_transfer_status(flow.ledger, ELENA, got["attempt_id"])
        self.tool(sender, "check_transfer_status", found)
        self.assertEqual(list(self.hooks._transfers[sender]), [found["reference"]])

    def test_claim_with_nothing_submitted_is_refused(self):
        with self.assertRaises(self.Retry):
            self.respond("nothing", "Your transfer is complete.")


if __name__ == "__main__":
    unittest.main()
