"""Offline checks for the Horizon Travel disruption guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
(The hook tests need rasa and are skipped under a bare python3; `make proof-full`
runs them in the project venv.)
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import recovery as hz  # noqa: E402

CASEBOOK_CONTRACT = PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "disruption-mode.json"
INES = "HT-PAX-3308"
TOMAS = "HT-PAX-5174"


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), hz.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """All ten authored variants: accepted, and each fact false, missing or the string "true"."""
        contract = hz.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                reason = hz.evaluate(variant["facts"], contract)
                outcome = ("blocked", reason) if reason else ("succeeded", "verified_fixture_receipt")
                self.assertEqual(outcome, (expected["status"], expected["reason"]))

    def test_all_three_rules_are_request_rules(self):
        self.assertEqual([r["field"] for r in hz.request_rules()],
                         ["incident_revision_current", "capacity_reserved", "recovery_channel_available"])


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_organisation(self):
        hz.assert_fictional(hz.load_data(), hz.load_contract())
        self.assertEqual(hz.allowed_organisations(hz.load_contract()), frozenset({"Horizon Travel"}))

    def test_any_other_organisation_is_refused_even_when_marked_fictional(self):
        data = hz.load_data()
        data["organisation"] = "Skyline Charter (fictional airline)"
        with self.assertRaises(hz.FictionalOrganisationError):
            hz.assert_fictional(data, hz.load_contract())

    def test_nested_organisation_fields_are_checked(self):
        data = hz.load_data()
        data["bookings"]["HT-5X7P1"]["partner"] = "Skyline Charter (fictional airline)"
        with self.assertRaises(hz.FictionalOrganisationError):
            hz.assert_fictional(data, hz.load_contract())
        data["bookings"]["HT-5X7P1"]["partner"] = "Horizon Travel (fictional partner desk)"
        hz.assert_fictional(data, hz.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for key, value in (("organisation", "Horizon Travel"), ("note", "Sample data.")):
            data = hz.load_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(hz.FictionalOrganisationError):
                hz.assert_fictional(data, hz.load_contract())


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        for passenger in hz.load_data()["passengers"]:
            profile = hz.session_profile(passenger)
            for key in ("passenger_id", "first_name", "affected_trips"):
                self.assertLessEqual(len(profile[key]), hz.MEMORY_VALUE_LIMIT, (passenger, key, profile[key]))

    def test_every_selection_memory_value_fits(self):
        data = hz.load_data()
        checked = 0
        for option_id, option in data["options"].items():
            passenger = data["bookings"][option["booking"]]["passenger_id"]
            svc = hz.Disruption()
            svc.revision = option["revisions"][0]
            svc.searches[option["booking"]] = {"revision": svc.revision, "options": [option_id]}
            result = hz.select_option(svc, passenger, option_id)
            self.assertEqual(result["status"], "selected", result)
            for key, value in hz.selection_memory(result).items():
                self.assertLessEqual(len(value), hz.MEMORY_VALUE_LIMIT, (key, value))
            checked += 1
        self.assertEqual(checked, len(data["options"]))

    def test_confirmation_question_reads_only_declared_memory(self):
        text = (PROJECT / "skills" / "disruption_recovery" / "responses.yml").read_text()
        memory = (PROJECT / "skills" / "disruption_recovery" / "memory.yml").read_text()
        for name in re.findall(r"\{(\w+)\}", text):
            self.assertIn(f"    {name}:", memory)


class ToolSurfaceTests(unittest.TestCase):
    """No tool takes a parameter that could carry a fact, a seat count or an outcome."""

    ALLOWED = {"booking", "option_id", "hold_id", "context"}

    def test_tool_parameters(self):
        files = [PROJECT / "skills" / "disruption_recovery" / "tools.py", PROJECT / "tools" / "horizon_shared.py"]
        seen = set()
        for path in files:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.AsyncFunctionDef) and any(
                        isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tool" for d in node.decorator_list):
                    params = {a.arg for a in node.args.args + node.args.kwonlyargs}
                    self.assertLessEqual(params, self.ALLOWED, (node.name, params))
                    seen.add(node.name)
        self.assertEqual(seen, {"find_recovery_options", "select_option", "hold_recovery_option",
                                "load_session_passenger", "get_incident_status", "check_hold", "release_hold",
                                "join_recovery_queue"})


class Flow:
    """find -> select -> hold, keeping the selection the way the tools do."""

    def __init__(self, conversation: str = "c1", passenger: str = INES) -> None:
        self.svc = hz.Disruption()
        self.conv = conversation
        self.passenger = passenger
        self.selected = None

    def find(self, words):
        self.selected = None
        return hz.find_recovery_options(self.svc, self.passenger, words)

    def select(self, option_id):
        result = hz.select_option(self.svc, self.passenger, option_id)
        self.selected = hz.selection_memory(result)["selected_option_id"] or None
        return result

    def hold(self, option_id=None):
        result = hz.hold_recovery_option(self.svc, self.passenger, self.selected, option_id or self.selected, self.conv)
        if result["status"] == "blocked":
            self.selected = None
        return result


class GuardTests(unittest.TestCase):
    def test_normal_hold_has_expiry_and_no_journey(self):
        f = Flow()
        found = f.find("my Chicago flight")
        self.assertEqual(found["status"], "options")
        self.assertTrue(found["seats_shown_is_not_a_hold"])
        f.select("OPT-ORD-315")
        held = f.hold()
        self.assertEqual((held["status"], held["effects"], held["journey_confirmed"]), ("held", 1, False))
        self.assertTrue(held["hold_id"].startswith("HT-HLD-"))
        self.assertEqual(held["expires"], "14:50 Boston time, 30 Sep")
        self.assertEqual(held["facts"], {"incident_revision_current": True, "capacity_reserved": True,
                                         "recovery_channel_available": True})

    def test_seat_count_shown_is_not_capacity(self):
        """The case's failure: two seats shown, none in the inventory."""
        f = Flow()
        found = f.find("Chicago")
        shown = {o["option_id"]: o["seats_shown"] for o in found["options"]}
        self.assertEqual(shown["OPT-ORD-319"], 2)
        f.select("OPT-ORD-319")
        held = f.hold()
        self.assertEqual((held["status"], held["reason"], held["effects"]), ("blocked", "capacity_not_reserved", 0))
        self.assertEqual(held["seats_now"], 0)
        self.assertFalse(any(h["state"] == "active" and h["booking"] == "HT-7Q4M2" for h in f.svc.holds.values()))

    def test_last_seat_can_be_held_once(self):
        f = Flow()
        f.find("Chicago")
        f.select("OPT-ORD-1204")
        first = f.hold()
        self.assertEqual(first["status"], "held")
        hz.release_hold(f.svc, INES, first["hold_id"])
        f.find("Chicago")
        f.select("OPT-ORD-1204")
        self.assertEqual(f.hold()["status"], "held")

    def test_stale_incident_revision(self):
        f = Flow()
        first = f.find("Denver")
        self.assertEqual(first["incident_revision"], 4)
        self.assertEqual([o["option_id"] for o in first["options"]], ["OPT-DEN-544"])
        f.select("OPT-DEN-544")
        held = f.hold()
        self.assertEqual((held["status"], held["reason"]), ("blocked", "stale_incident_state"))
        self.assertEqual(held["list_revision"], 4)
        self.assertEqual(held["incident_revision"], 5)
        # The list is void: the old option cannot be selected again.
        self.assertEqual(f.select("OPT-DEN-544")["reason"], "option_not_listed")
        second = f.find("Denver")
        self.assertEqual(second["incident_revision"], 5)
        self.assertEqual([o["option_id"] for o in second["options"]], ["OPT-DEN-548", "OPT-DEN-540"])
        f.select("OPT-DEN-548")
        self.assertEqual(f.hold()["status"], "held")

    def test_revision_change_voids_any_older_list(self):
        f = Flow()
        f.find("Chicago")  # revision 4
        f.find("Denver")  # revision 4, then the incident moves to 5
        f.select("OPT-ORD-315")
        self.assertEqual(f.hold()["reason"], "stale_incident_state")

    def test_partner_ticket_has_no_recovery_channel_and_keeps_no_seat(self):
        f = Flow()
        found = f.find("Toronto")
        self.assertIn("partner airline", found["recovery_channel"])
        before = f.svc.inventory["OPT-YYZ-712"]
        f.select("OPT-YYZ-712")
        held = f.hold()
        self.assertEqual((held["status"], held["reason"]), ("blocked", "no_recovery_channel"))
        self.assertTrue(held["facts"]["capacity_reserved"])
        self.assertEqual(f.svc.inventory["OPT-YYZ-712"], before, "the provisional hold must be released")
        queue = hz.join_recovery_queue(f.svc, INES, "Toronto", "c1")
        self.assertEqual(queue["reason"], "no_recovery_channel")

    def test_unverified_hold_service_holds_nothing_and_offers_the_queue(self):
        f = Flow()
        found = f.find("Washington")
        self.assertIn("unverified", found["hold_service"])
        f.select("OPT-DCA-209")
        held = f.hold()
        self.assertEqual((held["status"], held["reason"], held["hold_service"]),
                         ("blocked", "capacity_not_reserved", "unverified"))
        queued = hz.join_recovery_queue(f.svc, INES, "my DC trip", "c1")
        self.assertEqual((queued["status"], queued["seat_held"], queued["journey_confirmed"]), ("queued", False, False))
        again = hz.join_recovery_queue(f.svc, INES, "HT-3H6W4", "c1")
        self.assertEqual((again["queue_reference"], again["replay"]), (queued["queue_reference"], True))

    def test_one_hold_per_booking_and_release_before_search(self):
        """The case's correction: release the rejected hold before looking for a replacement."""
        f = Flow()
        f.find("Chicago")
        f.select("OPT-ORD-315")
        held = f.hold()
        blocked = f.find("Chicago")
        self.assertEqual((blocked["status"], blocked["reason"]), ("blocked", "hold_active"))
        self.assertEqual(blocked["active_hold"]["hold_id"], held["hold_id"])
        # A second hold on the same booking is refused too.
        f.svc.searches["HT-7Q4M2"] = {"revision": f.svc.revision, "options": ["OPT-ORD-1204"]}
        f.select("OPT-ORD-1204")
        self.assertEqual(f.hold()["reason"], "hold_active")
        released = hz.release_hold(f.svc, INES, held["hold_id"])
        self.assertEqual((released["status"], released["replay"]), ("released", False))
        self.assertEqual(hz.release_hold(f.svc, INES, held["hold_id"])["replay"], True)
        self.assertEqual(f.find("Chicago")["status"], "options")

    def test_existing_holds_by_identifier(self):
        svc = hz.Disruption()
        active = hz.check_hold(svc, INES, "ht-hld-4k7m")
        self.assertEqual((active["status"], active["expires"], active["journey_confirmed"]),
                         ("active", "15:10 Boston time, 30 Sep", False))
        self.assertEqual(hz.check_hold(svc, INES, "HT-HLD-31C2")["status"], "expired")
        self.assertEqual(hz.release_hold(svc, INES, "HT-HLD-31C2")["status"], "expired")
        # Another passenger's hold looks the same as one that does not exist.
        self.assertEqual(hz.check_hold(svc, INES, "HT-HLD-77Q9"), hz.check_hold(svc, INES, "HT-HLD-77Q9"))
        self.assertEqual(hz.check_hold(svc, INES, "HT-HLD-77Q9")["reason"], "hold_not_found")
        self.assertEqual(hz.check_hold(svc, INES, "HT-HLD-0000")["reason"], "hold_not_found")
        # The Miami booking's active hold blocks a new search until released.
        self.assertEqual(hz.find_recovery_options(svc, INES, "Miami")["reason"], "hold_active")
        # The held seat was the last one on HZ 902.
        self.assertEqual(svc.inventory["OPT-MIA-902"], 0)

    def test_other_passengers_booking_is_not_found(self):
        svc = hz.Disruption()
        for words in ("HT-8R1T6", "8R1T6", "booking HT-8R1T6 please"):
            with self.subTest(words=words):
                result = hz.find_recovery_options(svc, INES, words)
                self.assertEqual(result["reason"], "booking_not_found")
                self.assertNotIn("Tomas", json.dumps(result))
        self.assertEqual(hz.find_recovery_options(svc, INES, "HT-9Z9Z9")["reason"], "booking_not_found")
        self.assertEqual(hz.find_recovery_options(svc, None, "Chicago")["reason"], "no_signed_in_passenger")

    def test_booking_words_resolve(self):
        for words, ref in (("my Chicago flight", "HT-7Q4M2"), ("the O'Hare one", "HT-7Q4M2"), ("HZ 540", "HT-9D2K8"),
                           ("DCA", "HT-3H6W4"), ("ht-2l8n5", "HT-2L8N5"), ("Toronto", "HT-5X7P1")):
            with self.subTest(words=words):
                self.assertEqual(hz.resolve_booking(INES, words)[0], ref)
        ref, result = hz.resolve_booking(INES, "Chicago or Denver")
        self.assertIsNone(ref)
        self.assertEqual(result["reason"], "ambiguous_booking")

    def test_hold_needs_the_selected_option(self):
        f = Flow()
        f.find("Chicago")
        self.assertEqual(f.hold("OPT-ORD-315")["reason"], "option_not_selected")
        f.select("OPT-ORD-315")
        self.assertEqual(f.hold("OPT-ORD-1204")["reason"], "option_not_selected")
        self.assertEqual(f.select("OPT-ORD-315-OTHER")["reason"], "unknown_option")
        self.assertEqual(f.select("OPT-DEN-548")["reason"], "option_not_listed")


class ReceiptTests(unittest.TestCase):
    def test_every_outcome_the_passenger_must_see_has_a_receipt(self):
        f = Flow()
        f.find("Chicago")
        f.select("OPT-ORD-319")
        lag = hz.customer_receipt("hold_recovery_option", f.hold())
        self.assertIn("out of date", lag)
        f.select("OPT-ORD-315")
        held = f.hold()
        text = hz.customer_receipt("hold_recovery_option", held)
        self.assertIn(held["hold_id"], text)
        self.assertIn("14:50", text)
        self.assertIn("not a confirmed journey", text)
        released = hz.customer_receipt("release_hold", hz.release_hold(f.svc, INES, held["hold_id"]))
        self.assertIn(held["hold_id"], released)
        g = Flow()
        g.find("Washington")
        g.select("OPT-DCA-213")
        self.assertIn("can't promise a seat", hz.customer_receipt("hold_recovery_option", g.hold()))
        queued = hz.join_recovery_queue(g.svc, INES, "Washington", "c1")
        self.assertIn(queued["queue_reference"], hz.customer_receipt("join_recovery_queue", queued))

    def test_receipts_make_no_promise(self):
        f = Flow()
        f.find("Chicago")
        f.select("OPT-ORD-315")
        held = f.hold()
        texts = [hz.customer_receipt("hold_recovery_option", held),
                 hz.customer_receipt("release_hold", hz.release_hold(f.svc, INES, held["hold_id"])),
                 hz.customer_receipt("join_recovery_queue", hz.join_recovery_queue(f.svc, INES, "Chicago", "c1"))]
        for text in texts:
            self.assertEqual([k for k, _ in hz.promise_claims(text) if k == "commitment"], [], text)


class PromisePatternTests(unittest.TestCase):
    COMMITMENTS = [
        "You're booked on HZ 315 tomorrow at 07:10.",
        "You are now rebooked on the 12:25 flight.",
        "Your new flight is confirmed.",
        "Your seat is guaranteed.",
        "I've rebooked you on HZ 548.",
        "You'll definitely get a seat on the morning flight.",
        "The seat's yours.",
        "You're all set on HZ 1204.",
    ]
    HOLDS = ["I've held a seat on HZ 315 for you.", "Your seat is held until 14:50.", "The seat is now reserved."]
    CLEAN = [
        "This is a hold, not a confirmed journey.",
        "I can't promise a seat until the hold is placed.",
        "No seat is held on HZ 319.",
        "The seat count shown is not a hold.",
        "You're in the recovery queue at position 41.",
        "Once the hold is placed, the seat is held until it expires.",
        "Seat held: HZ 315 Boston to Chicago, hold HT-HLD-1A2B3C, until 14:50 Boston time, 30 Sep.",
        "That seat is no longer held for you.",
    ]

    def test_patterns(self):
        for text in self.COMMITMENTS:
            with self.subTest(text=text):
                self.assertEqual([k for k, _ in hz.promise_claims(text)], ["commitment"])
        for text in self.HOLDS:
            with self.subTest(text=text):
                self.assertEqual([k for k, _ in hz.promise_claims(text)], ["hold"])
        for text in self.CLEAN:
            with self.subTest(text=text):
                self.assertEqual(hz.promise_claims(text), [])

    def test_spec_metrics_match_the_library(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metrics = spec["bot_text_metrics"]
        self.assertEqual(metrics["commitment_promise"],
                         {"pattern": hz.COMMITMENT_PATTERN, "unless_before": hz.PROMISE_HEDGE_PATTERN})
        self.assertEqual(metrics["hold_claim"],
                         {"pattern": hz.HOLD_CLAIM_PATTERN, "unless_before": hz.PROMISE_HEDGE_PATTERN})

    def test_spec_keeps_the_shared_harness_keys(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        self.assertIn("engine_errors", spec)
        self.assertNotIn("utter_on_user_denial",
                         (PROJECT / "skills" / "disruption_recovery" / "skill.md").read_text())


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
        return asyncio.run(coro)

    def respond(self, sender, text):
        return self.run_hook(self.hooks.block_unbacked_promises(self.Model(sender_id=sender, text=text)))

    def tool(self, sender, name, result):
        # The engine passes the result as serialized JSON text, as dispatched.
        self.run_hook(self.hooks.remember_hold_states(
            self.Tool(sender_id=sender, tool_name=name, arguments={}, value=json.dumps(result))))

    def test_commitment_is_retried_then_replaced_even_with_a_hold(self):
        sender = "commit"
        f = Flow(sender)
        f.find("Chicago")
        f.select("OPT-ORD-315")
        held = f.hold()
        self.tool(sender, "hold_recovery_option", held)
        for _ in range(self.hooks.MAX_CONSECUTIVE_RETRIES):
            with self.assertRaises(self.Retry):
                self.respond(sender, "Great news, you're booked on HZ 315 tomorrow.")
        out = self.respond(sender, "Great news, you're booked on HZ 315 tomorrow.")
        self.assertIn(held["hold_id"], out.text)
        self.assertIn("not a confirmed journey", out.text)
        self.assertEqual(hz.promise_claims(out.text), [])

    def test_hold_claim_needs_an_active_hold(self):
        sender = "hold"
        with self.assertRaises(self.Retry):
            self.respond(sender, "I've held a seat on HZ 319 for you.")
        f = Flow(sender)
        f.find("Chicago")
        f.select("OPT-ORD-315")
        held = f.hold()
        self.tool(sender, "hold_recovery_option", held)
        out = self.respond(sender, "Your seat is held until 14:50.")
        self.assertEqual(out.text, "Your seat is held until 14:50.")
        self.tool(sender, "release_hold", hz.release_hold(f.svc, INES, held["hold_id"]))
        with self.assertRaises(self.Retry):
            self.respond(sender, "Your seat is held until 14:50.")

    def test_existing_active_hold_backs_a_hold_claim(self):
        sender = "existing"
        self.tool(sender, "check_hold", hz.check_hold(hz.Disruption(), INES, "HT-HLD-4K7M"))
        out = self.respond(sender, "Your seat on HZ 902 is held until 15:10.")
        self.assertEqual(out.text, "Your seat on HZ 902 is held until 15:10.")

    def test_clean_text_passes(self):
        out = self.respond("clean", "No seat is held yet. A seat count is not a hold.")
        self.assertEqual(out.text, "No seat is held yet. A seat count is not a hold.")


if __name__ == "__main__":
    unittest.main()
