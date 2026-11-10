"""Offline checks for the Willow Shop subscription-change guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import subscriptions as ws  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "retail-loyalty.json"
SPEC = PROJECT / "case-build" / "conversations.json"
RESPONSES = PROJECT / "skills" / "subscription_change" / "responses.yml"
ME = ws.SESSION_MEMBER_ID
PLUS, COFFEE, PET, STYLE, OTHER = "WS-SUB-3301", "WS-SUB-3302", "WS-SUB-3303", "WS-SUB-3304", "WS-SUB-4410"


class UserUttered:  # stand-ins named like Rasa's events
    def __init__(self, text: str) -> None:
        self.text = text


class BotUttered:
    def __init__(self, text: str, utter_action: str | None = None) -> None:
        self.text = text
        self.metadata = {ws.UTTER_ACTION_KEY: utter_action} if utter_action else {}


def question_for(memory: dict) -> str:
    """What the engine's question says, filled from memory as responses.yml does."""
    return (f"Please confirm this change to your {memory['change_subscription']}: {memory['change_label']}. "
            f"It takes effect {memory['change_effective']}. What changes for you: {memory['change_entitlements']}. "
            f"(Change {memory['change_tag']}.) Shall I make this change? If you meant a different change, say which.")


def asked_and_answered(memory: dict, answer: str = "Yes.") -> ws.Conversation:
    return conversation_from_events([
        UserUttered("/session_start"),
        UserUttered("Please change my subscription."),
        BotUttered(question_for(memory), ws.CONFIRM_UTTER),
        UserUttered(answer),
    ])


def select(svc: ws.SubscriptionService, sub: str, change: str) -> tuple[dict, dict]:
    return ws.select_subscription_change(svc, ME, sub, change)


def apply(svc: ws.SubscriptionService, sub: str, change: str, memory: dict, conv=None, cid: str = "c1") -> dict:
    return ws.apply_subscription_change(svc, ME, memory, conv or asked_and_answered(memory), sub, change, cid)


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), ws.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = ws.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                request = ws.evaluate(variant["facts"], "request", contract)
                receipt = ws.evaluate(variant["facts"], "receipt", contract)
                if expected["status"] == "blocked":
                    self.assertEqual(request, expected["reason"])
                elif expected["status"] == "pending":
                    self.assertIsNone(request)
                    self.assertEqual(receipt, expected["reason"])
                else:
                    self.assertIsNone(request)
                    self.assertIsNone(receipt)

    def test_string_true_is_not_true(self):
        facts = {"change_type_confirmed": True, "entitlement_delta_disclosed": "true"}
        self.assertEqual(ws.evaluate(facts, "request"), "benefit_loss_hidden")


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_retailer(self):
        ws.assert_fictional(ws.load_data(), ws.load_contract())
        self.assertEqual(ws.ORGANISATION, ws.load_contract()["organisation"])
        self.assertEqual(ws.allowed_organisations(ws.load_contract()), frozenset({"Willow Shop"}))

    def test_any_other_organisation_is_refused_even_when_marked_fictional(self):
        data = ws.load_data()
        data["organisation"] = "Birch Market (fictional retailer)"
        with self.assertRaises(ws.FictionalOrganisationError):
            ws.assert_fictional(data, ws.load_contract())

    def test_nested_organisation_fields_are_checked(self):
        data = ws.load_data()
        data["subscriptions"][PLUS]["merchant"] = "Birch Market (fictional retailer)"
        with self.assertRaises(ws.FictionalOrganisationError):
            ws.assert_fictional(data, ws.load_contract())
        data["subscriptions"][PLUS]["merchant"] = "Willow Shop (fictional retailer)"
        ws.assert_fictional(data, ws.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for key, value in (("organisation", "Willow Shop"), ("note", "Sample data.")):
            data = ws.load_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ws.FictionalOrganisationError):
                ws.assert_fictional(data, ws.load_contract())


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        profile = ws.member_profile(ws.SubscriptionService())
        for key in ("member_id", "first_name", "subscription_list"):
            self.assertLessEqual(len(profile[key]), ws.MEMORY_VALUE_LIMIT, key)

    def test_every_option_and_revision_fits(self):
        """Every change on every subscription, before and after a fixture update, as select writes it."""
        data = ws.load_data()
        for sub_id, sub in data["subscriptions"].items():
            revisions = [(sub["revision"], sub["options"])]
            if sub.get("update_on_first_command"):
                update = sub["update_on_first_command"]
                revisions.append((update["revision"], update["options"]))
            for revision, options in revisions:
                for change in ws.CHANGE_TYPES:
                    with self.subTest(sub=sub_id, revision=revision, change=change):
                        values = {
                            "change_subscription": f"{sub['label']} ({sub_id})",
                            "change_tag": ws.change_tag(sub_id, change, revision),
                            "change_label": ws.CHANGE_LABELS[change],
                            "change_effective": ws.effective_text(options[change]["effective_at"]),
                            "change_entitlements": options[change]["entitlements"],
                        }
                        self.assertTrue(ws.memory_values_fit(values), values)

    def test_engine_cap_is_what_the_limit_assumes(self):
        try:
            from rasa.mantle.prompts.memory_lines import MAX_MEMORY_VALUE_LENGTH
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")
        self.assertEqual(MAX_MEMORY_VALUE_LENGTH, ws.MEMORY_VALUE_LIMIT)

    def test_question_template_reads_every_memory_key(self):
        text = RESPONSES.read_text()
        for key in ws.MEMORY_KEYS:
            self.assertIn("{" + key + "}", text, key)
        self.assertNotIn("utter_on_user_denial", (PROJECT / "skills" / "subscription_change" / "skill.md").read_text())


class SubscriptionTests(unittest.TestCase):
    def test_subscriptions_by_words_and_number(self):
        svc = ws.SubscriptionService()
        self.assertEqual(ws.resolve_subscription(svc, ME, "my Willow Plus membership")[0], PLUS)
        self.assertEqual(ws.resolve_subscription(svc, ME, "the coffee one")[0], COFFEE)
        self.assertEqual(ws.resolve_subscription(svc, ME, "dog food autoship")[0], PET)
        self.assertEqual(ws.resolve_subscription(svc, ME, "Style Box")[0], STYLE)
        self.assertEqual(ws.resolve_subscription(svc, ME, "WS-SUB-3302")[0], COFFEE)
        self.assertEqual(ws.resolve_subscription(svc, ME, "3301")[0], PLUS)

    def test_subscription_alone_is_ambiguous(self):
        sub, result = ws.resolve_subscription(ws.SubscriptionService(), ME, "my subscription")
        self.assertIsNone(sub)
        self.assertEqual(result["reason"], "which_subscription")
        self.assertEqual(len(result["candidates"]), 4)

    def test_someone_elses_subscription_and_a_missing_one_get_the_same_answer(self):
        svc = ws.SubscriptionService()
        other = ws.compare_subscription_changes(svc, ME, OTHER)
        missing = ws.compare_subscription_changes(svc, ME, "WS-SUB-9999")
        self.assertEqual(other["status"], "not_found")
        self.assertEqual(other, missing)

    def test_compare_lists_three_options_with_dates(self):
        result = ws.compare_subscription_changes(ws.SubscriptionService(), ME, "Willow Plus")
        self.assertEqual([o["change_type"] for o in result["options"]], list(ws.CHANGE_TYPES))
        stop, _, cancel = result["options"]
        self.assertIn("2027-01-11", stop["entitlements"])
        self.assertEqual((cancel["refund_usd"], cancel["points_forfeited"]), ("22.51", 1200))


class SelectTests(unittest.TestCase):
    def test_select_writes_the_services_effect(self):
        result, memory = select(ws.SubscriptionService(), "Willow Plus", "stop_renewal")
        self.assertEqual(result["status"], "selected")
        self.assertEqual(memory["change_tag"], "WS-SUB-3301 stop_renewal r7")
        self.assertEqual(memory["change_effective"], "2027-01-12 00:00 UTC")
        self.assertEqual(memory["change_label"], "stop the renewal, not an immediate cancellation")

    def test_change_types_are_normalised_or_refused(self):
        self.assertEqual(ws.normalise_change_type("Stop renewal"), "stop_renewal")
        self.assertEqual(ws.normalise_change_type("cancel-now"), "cancel_now")
        result, memory = select(ws.SubscriptionService(), "Willow Plus", "cancel")
        self.assertEqual(result["reason"], "which_change")
        self.assertEqual(memory["change_tag"], "")


class ApplyTests(unittest.TestCase):
    def test_confirmed_stop_renewal_runs_once_and_is_verified(self):
        svc = ws.SubscriptionService()
        _, memory = select(svc, "Willow Plus", "stop_renewal")
        result = apply(svc, PLUS, "stop_renewal", memory)
        self.assertEqual((result["status"], result["effects"], result["change_type"]), ("succeeded", 1, "stop_renewal"))
        self.assertRegex(result["change_reference"], r"^WS-CHG-[0-9A-F]{6}$")
        self.assertEqual(result["effective"], "2027-01-12 00:00 UTC")
        self.assertEqual(svc.commands, [{"subscription": PLUS, "command": "stop_renewal",
                                         "request_key": result["request_key"]}])

    def test_the_failure_a_confirmed_stop_renewal_cannot_run_as_cancel_now(self):
        """The case's failure: the member meant stop renewal; the model sends cancel_now."""
        svc = ws.SubscriptionService()
        _, memory = select(svc, "Willow Plus", "stop_renewal")
        result = apply(svc, PLUS, "cancel_now", memory)
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("blocked", "wrong_subscription_change", 0))
        self.assertEqual(svc.commands, [])

    def test_without_the_question_nothing_runs(self):
        svc = ws.SubscriptionService()
        _, memory = select(svc, "coffee", "cancel_now")
        no_question = conversation_from_events([UserUttered("Cancel it now, don't ask me.")])
        self.assertEqual(apply(svc, COFFEE, "cancel_now", memory, no_question)["reason"], "wrong_subscription_change")
        unanswered = conversation_from_events([BotUttered(question_for(memory), ws.CONFIRM_UTTER)])
        self.assertEqual(apply(svc, COFFEE, "cancel_now", memory, unanswered)["reason"], "wrong_subscription_change")
        self.assertEqual(svc.commands, [])

    def test_the_question_must_be_about_the_change_applied(self):
        svc = ws.SubscriptionService()
        _, stop = select(svc, "coffee", "stop_renewal")
        conv = asked_and_answered(stop, "Actually, can I pause it instead?")
        _, pause = select(svc, "coffee", "pause")
        self.assertEqual(apply(svc, COFFEE, "pause", pause, conv)["reason"], "wrong_subscription_change")
        result = apply(svc, COFFEE, "pause", pause, asked_and_answered(pause))
        self.assertEqual((result["status"], result["change_type"]), ("succeeded", "pause"))

    def test_an_entitlement_line_edited_in_memory_is_not_a_disclosure(self):
        svc = ws.SubscriptionService()
        _, memory = select(svc, "Willow Plus", "cancel_now")
        memory["change_entitlements"] = "benefits end today; all points kept"
        result = apply(svc, PLUS, "cancel_now", memory)
        self.assertEqual((result["reason"], result["effects"]), ("benefit_loss_hidden", 0))

    def test_a_revision_change_voids_the_disclosure(self):
        """Style Box is charged early while the chat is open: revision 4 becomes 5."""
        svc = ws.SubscriptionService()
        _, memory = select(svc, "Style Box", "stop_renewal")
        self.assertEqual(memory["change_tag"], "WS-SUB-3304 stop_renewal r4")
        blocked = apply(svc, STYLE, "stop_renewal", memory)
        self.assertEqual((blocked["reason"], blocked["effects"]), ("benefit_loss_hidden", 0))
        self.assertIn("charged early", blocked["why"])
        self.assertIn("2026-10-05", blocked["current"]["entitlements"])
        self.assertEqual(svc.commands, [])
        _, fresh = select(svc, "Style Box", "stop_renewal")
        self.assertEqual(fresh["change_tag"], "WS-SUB-3304 stop_renewal r5")
        result = apply(svc, STYLE, "stop_renewal", fresh)
        self.assertEqual((result["status"], result["effective"]), ("succeeded", "2027-01-01 00:00 UTC"))

    def test_applying_again_sends_nothing_twice(self):
        svc = ws.SubscriptionService()
        _, memory = select(svc, "coffee", "pause")
        first = apply(svc, COFFEE, "pause", memory)
        again = apply(svc, COFFEE, "pause", memory)
        self.assertEqual(again["change_reference"], first["change_reference"])
        self.assertEqual((again["replay"], again["effects"]), (True, 0))
        self.assertEqual(len(svc.commands), 1)
        self.assertIsNone(ws.customer_receipt("apply_subscription_change", again))

    def test_a_second_change_on_the_same_subscription_is_refused(self):
        svc = ws.SubscriptionService()
        _, memory = select(svc, "Willow Plus", "stop_renewal")
        apply(svc, PLUS, "stop_renewal", memory)
        result, _ = select(svc, "Willow Plus", "cancel_now")
        self.assertEqual(result["reason"], "change_already_recorded")
        blocked = apply(svc, PLUS, "cancel_now", memory)
        self.assertEqual((blocked["reason"], blocked["effects"]), ("change_already_recorded", 0))
        self.assertEqual(len(svc.commands), 1)

    def test_no_tool_takes_dates_amounts_or_facts(self):
        """The model can pass words, a change type or a note; never a date, an amount, a revision or a fact."""
        forbidden = {"date", "effective", "effective_at", "amount", "refund", "refund_usd", "points", "revision",
                     "member_id", "entitlements", "request_key", "change_type_confirmed",
                     "entitlement_delta_disclosed", "change_receipt_verified", "facts"}
        for path in (PROJECT / "skills" / "subscription_change" / "tools.py", PROJECT / "tools" / "willow_session.py"):
            tree = ast.parse(path.read_text())
            for node in tree.body:
                if isinstance(node, ast.AsyncFunctionDef) and node.decorator_list:
                    params = {a.arg for a in node.args.args} - {"context"}
                    with self.subTest(tool=node.name):
                        self.assertFalse(params & forbidden, params)


class ReceiptPhaseTests(unittest.TestCase):
    def test_unknown_result_is_pending_and_recovered_without_a_second_command(self):
        """Pet Pantry: the first command's answer is lost, though the service applied it."""
        svc = ws.SubscriptionService()
        _, memory = select(svc, "pet food", "stop_renewal")
        pending = apply(svc, PET, "stop_renewal", memory)
        self.assertEqual((pending["status"], pending["reason"], pending["effects"]),
                         ("pending", "change_not_recorded", 1))
        self.assertIsNone(ws.customer_receipt("apply_subscription_change", pending))
        again = apply(svc, PET, "stop_renewal", memory)
        self.assertEqual((again["reason"], again["effects"]), ("change_pending", 0))
        result, _ = select(svc, "pet food", "cancel_now")
        self.assertEqual(result["reason"], "change_pending")
        status = ws.check_change_status(svc, ME, PET, "c1")
        self.assertEqual((status["status"], status["verified_by"], status["effects"]),
                         ("succeeded", "status_check", 0))
        self.assertEqual(status["original_revision"], 3)
        self.assertEqual(len(svc.commands), 1, "recovery must not send another command")
        self.assertIn(status["change_reference"], ws.customer_receipt("check_change_status", status))

    def test_an_answer_with_another_command_is_not_a_receipt(self):
        svc = ws.SubscriptionService()
        svc.response_filter = lambda answer: {**answer, "command": "cancel_now"}
        _, memory = select(svc, "coffee", "stop_renewal")
        result = apply(svc, COFFEE, "stop_renewal", memory)
        self.assertEqual((result["status"], result["reason"]), ("pending", "change_not_recorded"))

    def test_an_answer_with_other_dates_is_not_a_receipt(self):
        svc = ws.SubscriptionService()
        svc.response_filter = lambda answer: {**answer, "effective_at": "2026-09-30T09:00:00+00:00"}
        _, memory = select(svc, "Willow Plus", "stop_renewal")
        self.assertEqual(apply(svc, PLUS, "stop_renewal", memory)["status"], "pending")

    def test_status_with_nothing_sent(self):
        self.assertEqual(ws.check_change_status(ws.SubscriptionService(), ME, COFFEE, "c1")["status"],
                         "no_change_requested")


class ReceiptTests(unittest.TestCase):
    def test_receipt_has_reference_effective_time_and_what_is_kept(self):
        svc = ws.SubscriptionService()
        _, memory = select(svc, "Willow Plus", "cancel_now")
        result = apply(svc, PLUS, "cancel_now", memory)
        text = ws.customer_receipt("apply_subscription_change", result)
        self.assertIn(result["change_reference"], text)
        self.assertIn("Cancelled now, effective 2026-09-30 09:00 UTC", text)
        self.assertIn("1,200 Plus bonus points are forfeited", text)
        self.assertIn("Refund: $22.51.", text)

    def test_blocked_results_send_nothing(self):
        self.assertIsNone(ws.customer_receipt("apply_subscription_change", {"status": "blocked"}))

    def test_support_receipt_and_no_resend_on_replay(self):
        svc = ws.SubscriptionService()
        first = ws.route_subscription_support(svc, ME, PLUS, "Wants a refund after stopping renewal.", "c1")
        self.assertRegex(ws.customer_receipt("route_subscription_support", first), r"WS-SUP-[0-9A-F]{6}")
        again = ws.route_subscription_support(svc, ME, PLUS, "Again.", "c1")
        self.assertTrue(again["replay"])
        self.assertIsNone(ws.customer_receipt("route_subscription_support", again))

    def test_tool_sends_receipt_is_on(self):
        self.assertTrue(ws.TOOL_SENDS_RECEIPT)

    def test_receipts_state_no_figure_the_result_lacks(self):
        svc = ws.SubscriptionService()
        for sub, change in ((PLUS, "stop_renewal"), (COFFEE, "pause"), (PLUS, "cancel_now")):
            svc = ws.SubscriptionService()
            _, memory = select(svc, sub, change)
            result = apply(svc, sub, change, memory)
            dates, amounts = ws.known_figures(result)
            with self.subTest(sub=sub, change=change):
                self.assertEqual(ws.unsupported_figures(ws.customer_receipt("apply_subscription_change", result),
                                                        dates, amounts), [])


class WordsTests(unittest.TestCase):
    DATES = {(2027, 1, 11), (2027, 1, 12), (2026, 9, 30)}
    AMOUNTS = {Decimal("22.51"), Decimal("79.00")}

    def test_dates_in_every_common_form(self):
        found = {(y, m, d) for y, m, d, _ in ws.dates_in(
            "2027-01-11, January 12, 2027, 12 Jan 2027, Oct 8, the 3rd of October, 1/11/2027")}
        self.assertEqual(found, {(2027, 1, 11), (2027, 1, 12), (None, 10, 8), (None, 10, 3)})

    def test_invented_dates_and_amounts_are_caught(self):
        for text in ("You'll keep your benefits until January 31, 2027.", "Your refund will be $30.00.",
                     "Access ends on 2026-10-31."):
            with self.subTest(text=text):
                self.assertTrue(ws.unsupported_figures(text, self.DATES, self.AMOUNTS))

    def test_service_figures_and_refusals_pass(self):
        for text in ("Stopping renewal keeps Plus until January 11, 2027, and there is no charge on 2027-01-12.",
                     "Cancelling now ends it today and refunds $22.51.",
                     "I can’t pause it until March 1, the service offers three months.",
                     "The $30 refund you mentioned is not something I can give."):
            with self.subTest(text=text):
                self.assertEqual(ws.unsupported_figures(text, self.DATES, self.AMOUNTS), [])

    def test_typographic_apostrophe_is_a_hedge(self):
        self.assertEqual(ws.unsupported_figures("I can’t extend it to Feb 28.", self.DATES, self.AMOUNTS), [])
        self.assertTrue(ws.unsupported_figures("I’ll extend it to Feb 28.", self.DATES, self.AMOUNTS))

    def test_thousands_and_times_stay_whole(self):
        self.assertEqual(ws.unsupported_figures("Effective 2027-01-12 00:00 UTC.", self.DATES, self.AMOUNTS), [])
        self.assertTrue(ws.unsupported_figures("You get $1,200 back.", self.DATES, self.AMOUNTS))

    def test_known_figures_reads_tool_results(self):
        result = ws.compare_subscription_changes(ws.SubscriptionService(), ME, "Willow Plus")
        dates, amounts = ws.known_figures(json.dumps(result))
        self.assertIn((2027, 4, 12), dates)
        self.assertIn(Decimal("22.51"), amounts)

    def test_spec_reference_pattern(self):
        metrics = json.loads(SPEC.read_text())["bot_text_metrics"]
        self.assertEqual(metrics["change_reference"], r"\bWS-CHG-[0-9A-F]{6}\b")


class ConversationTests(unittest.TestCase):
    def test_question_and_answer_are_read_from_events(self):
        conv = conversation_from_events([
            UserUttered("/session_start"), BotUttered("Hello."), UserUttered("Stop Plus renewing."),
            BotUttered("Q about WS-SUB-3301 stop_renewal r7", ws.CONFIRM_UTTER),
        ])
        self.assertEqual(conv.confirmation_question, "Q about WS-SUB-3301 stop_renewal r7")
        self.assertFalse(conv.confirmation_answered)
        self.assertEqual(conv.user_messages, ("Stop Plus renewing.",))


class HookTests(unittest.TestCase):
    def setUp(self):
        try:
            import hooks  # noqa: F401
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")

    def test_hook_remembers_figures_and_flags_only_invented_ones(self):
        import hooks

        dates, amounts = set(), set()
        hooks.remember(dates, amounts, json.dumps(ws.compare_subscription_changes(ws.SubscriptionService(), ME, PLUS)))
        self.assertEqual(hooks.problems("Cancelling now refunds $22.51 and ends Plus today.", dates, amounts), [])
        self.assertTrue(hooks.problems("You keep Plus until March 31, 2027.", dates, amounts))
        self.assertEqual(ws.dates_in(hooks.FALLBACK_TEXT), [])


if __name__ == "__main__":
    unittest.main()
