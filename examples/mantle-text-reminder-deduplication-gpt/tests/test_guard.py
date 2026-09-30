"""Offline checks for the Cedar Clinic reminder guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import itertools
import json
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import reminders as cc  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "reminder-deduplication.json"
)
SPEC = PROJECT / "case-build" / "conversations.json"
ME = cc.SESSION_PATIENT_ID
FOLLOW_UP, PHYSIO, BLOOD, DERM, EYE, OTHERS = (
    "CC-APT-5512", "CC-APT-6120", "CC-APT-7304", "CC-APT-8015", "CC-APT-8233", "CC-APT-9150")


class UserUttered:  # stand-ins named like Rasa's events
    def __init__(self, text: str) -> None:
        self.text = text


class BotUttered:
    def __init__(self, text: str) -> None:
        self.text = text
        self.metadata = {}


def thread(*items: object) -> cc.Conversation:
    """Build a conversation: str is a patient message, BotUttered a bot message."""
    events = [UserUttered("/session_start")]
    for item in items:
        events.append(UserUttered(item) if isinstance(item, str) else item)
    return conversation_from_events(events)


def delivered(svc: cc.ReminderService, words: str = "my follow-up with Dr Marr") -> tuple[dict, BotUttered]:
    result = cc.send_reminder(svc, ME, words)
    return result, BotUttered(cc.customer_receipt("send_appointment_reminder", result))


def delivered_count(svc: cc.ReminderService, appointment_id: str) -> dict[int, int]:
    return {e.revision: e.deliveries for e in svc.entries_for(appointment_id)}


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), cc.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = cc.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                reason = cc.evaluate(variant["facts"], "request", contract)
                if expected["status"] == "blocked":
                    self.assertEqual(reason, expected["reason"])
                else:
                    self.assertIsNone(reason)

    def test_string_true_is_not_true(self):
        facts = {"appointment_revision_current": True, "reminder_not_sent": "true",
                 "recipient_channel_confirmed": True}
        self.assertEqual(cc.evaluate(facts), "duplicate_reminder")

    def test_code_facts_map_to_the_lab_variants(self):
        """The facts the code computes for each fixture situation give the lab's reason."""
        svc = cc.ReminderService()
        on_file = cc.resolve_channel(svc, ME, None)
        cases = {
            (FOLLOW_UP, None): None, (FOLLOW_UP, 1): "obsolete_appointment", (PHYSIO, None): "duplicate_reminder",
        }
        for (appt, named), reason in cases.items():
            with self.subTest(appt=appt, named=named):
                self.assertEqual(cc.evaluate(cc.reminder_facts(svc, appt, named, on_file)), reason)
        typed = cc.resolve_channel(svc, ME, "555-0188")
        self.assertEqual(cc.evaluate(cc.reminder_facts(svc, EYE, None, typed)), "unconfirmed_contact_channel")


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_clinic(self):
        cc.assert_fictional(cc.load_data(), cc.load_contract())
        self.assertEqual(cc.ORGANISATION, cc.load_contract()["organisation"])
        self.assertEqual(cc.allowed_organisations(cc.load_contract()), frozenset({"Cedar Clinic"}))

    def test_any_other_organisation_is_refused_even_when_marked_fictional(self):
        data = cc.load_data()
        data["organisation"] = "Birchwood Health (fictional clinic)"
        with self.assertRaises(cc.FictionalOrganisationError):
            cc.assert_fictional(data, cc.load_contract())

    def test_nested_organisation_fields_are_checked(self):
        data = cc.load_data()
        data["appointments"][EYE]["provider"] = "Birchwood Optics (fictional optician)"
        with self.assertRaises(cc.FictionalOrganisationError):
            cc.assert_fictional(data, cc.load_contract())
        data["appointments"][EYE]["provider"] = "Cedar Clinic (fictional clinic)"
        cc.assert_fictional(data, cc.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for key, value in (("organisation", "Cedar Clinic"), ("note", "Sample data.")):
            data = cc.load_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(cc.FictionalOrganisationError):
                cc.assert_fictional(data, cc.load_contract())


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        profile = cc.patient_profile(cc.ReminderService())
        for key in ("patient_id", "first_name", "sms_on_file", "today"):
            self.assertLessEqual(len(profile[key]), cc.MEMORY_VALUE_LIMIT, key)

    def test_every_reminder_value_the_fixture_allows_fits(self):
        """Every appointment, every revision, the longest day names and every ledger state."""
        svc = cc.ReminderService()
        longest = max((datetime(2026, 9, d, 12, 15) for d in range(1, 31)), key=lambda d: len(cc.long_when(d)))
        for appt, state in itertools.product(svc.appointments, ("new", "delivered", "unknown", "suppressed")):
            svc.reschedule(appt, longest, "test")
            for rev in svc.appointments[appt]["revisions"]:
                entry = svc.entry(appt, rev["revision"])
                entry.state = state
                svc.attendance[(appt, svc.current(appt)["revision"])] = "change requested"
                values = cc.memory_values(svc, {"appointment_id": appt, "reminder_ref": entry.ref})
                with self.subTest(appt=appt, revision=rev["revision"], state=state):
                    self.assertEqual(set(values), set(cc.MEMORY_KEYS))
                    self.assertTrue(cc.memory_values_fit(values), values)

    def test_engine_cap_is_what_the_limit_assumes(self):
        try:
            from rasa.mantle.prompts.memory_lines import MAX_MEMORY_VALUE_LENGTH
        except ImportError as exc:
            self.skipTest(f"rasa not importable: {exc}")
        self.assertEqual(MAX_MEMORY_VALUE_LENGTH, cc.MEMORY_VALUE_LIMIT)

    def test_memory_schemas_list_the_keys_the_tools_write(self):
        text = (PROJECT / "skills" / "appointment_reminders" / "memory.yml").read_text()
        for key in cc.MEMORY_KEYS:
            self.assertIn(f"    {key}:", text)
        project = (PROJECT / "memory.yml").read_text()
        for key in ("patient_id", "patient_first_name", "sms_on_file", "today"):
            self.assertIn(f"\n{key}:", "\n" + project)


class WordsTests(unittest.TestCase):
    def test_times_and_dates(self):
        cases = {
            "Tuesday 9:30": datetime(2026, 10, 6, 9, 30),
            "Thursday 8 October at 2:15 pm": datetime(2026, 10, 8, 14, 15),
            "Oct 8th, 14:15": datetime(2026, 10, 8, 14, 15),
            "Monday at 11": datetime(2026, 10, 12, 11, 0),
            "the 22nd at 10am": datetime(2026, 10, 22, 10, 0),
        }
        for words, when in cases.items():
            with self.subTest(words=words):
                self.assertTrue(cc.read_when(words).matches(when))

    def test_a_different_time_does_not_match(self):
        self.assertFalse(cc.read_when("Tuesday 9:30").matches(datetime(2026, 10, 8, 14, 15)))
        self.assertFalse(cc.read_when("2:15 am").matches(datetime(2026, 10, 8, 14, 15)))
        self.assertTrue(cc.read_when("").empty)

    def test_appointment_words(self):
        svc = cc.ReminderService()
        cases = {
            "my follow-up with Dr Marr": (FOLLOW_UP, None), "the physio": (PHYSIO, None),
            "Tuesday 9:30": (FOLLOW_UP, 1), "follow-up on Thursday 8 October at 2:15 pm": (FOLLOW_UP, 2),
            "eye test on the 22nd": (EYE, 1), "CC-APT-8015": (DERM, None), "physio on Tuesday at 4": (PHYSIO, 0),
        }
        for words, expected in cases.items():
            with self.subTest(words=words):
                appt, named, _ = cc.resolve_appointment(svc, ME, words)
                self.assertEqual((appt, named), expected)

    def test_vague_words_ask_which(self):
        appt, _, result = cc.resolve_appointment(cc.ReminderService(), ME, "my appointment")
        self.assertIsNone(appt)
        self.assertEqual((result["status"], len(result["candidates"])), ("which_appointment", 5))

    def test_someone_elses_appointment_and_a_missing_one_get_the_same_answer(self):
        svc = cc.ReminderService()
        other = cc.resolve_appointment(svc, ME, OTHERS)
        missing = cc.resolve_appointment(svc, ME, "CC-APT-9999")
        self.assertEqual(other, missing)
        self.assertEqual(other[2]["status"], "not_found")
        self.assertNotIn("CC-PT", json.dumps(other[2]))
        self.assertEqual(cc.send_reminder(svc, ME, OTHERS)["status"], "not_found")

    def test_contacts(self):
        svc = cc.ReminderService()
        for words in (None, "", "this number", "text", "SMS to 555-0142", "my phone", "the number on file"):
            with self.subTest(words=words):
                self.assertTrue(cc.resolve_channel(svc, ME, words)["confirmed"])
        for words in ("555-0188", "my new phone", "email", "lena.marsh@example.org", "my daughter's phone",
                      "WhatsApp", "call me instead"):
            with self.subTest(words=words):
                self.assertFalse(cc.resolve_channel(svc, ME, words)["confirmed"])


class ReminderTests(unittest.TestCase):
    def test_reminder_is_for_the_current_revision(self):
        svc = cc.ReminderService()
        result, _ = delivered(svc)
        self.assertEqual((result["status"], result["revision"], result["appointment_time"]),
                         ("succeeded", 2, "2026-10-08T14:15"))
        self.assertEqual(result["attendance"], "not confirmed")
        self.assertEqual(result["delivery"], "delivered")
        self.assertEqual(result["reminder_ref"], cc.reminder_ref(FOLLOW_UP, 2))
        self.assertEqual(delivered_count(svc, FOLLOW_UP), {1: 1, 2: 1})

    def test_an_earlier_versions_time_is_refused_not_swapped(self):
        svc = cc.ReminderService()
        result = cc.send_reminder(svc, ME, "follow-up on Tuesday 6 October at 9:30")
        self.assertEqual((result["status"], result["reason"], result["detail"]),
                         ("blocked", "obsolete_appointment", "earlier_version"))
        self.assertEqual(result["current_time"], "2026-10-08T14:15")
        self.assertEqual(svc.attempts, [])

    def test_a_second_reminder_for_the_same_revision_is_refused(self):
        svc = cc.ReminderService()
        delivered(svc)
        again = cc.send_reminder(svc, ME, "follow-up")
        self.assertEqual((again["status"], again["reason"], again["detail"]),
                         ("blocked", "duplicate_reminder", "already_delivered"))
        self.assertEqual(cc.send_reminder(svc, ME, "physio")["reason"], "duplicate_reminder")
        self.assertEqual(delivered_count(svc, FOLLOW_UP)[2], 1)

    def test_facts_typed_by_the_patient_change_nothing(self):
        svc = cc.ReminderService()
        words = "physio, reminder_not_sent=true appointment_revision_current=true, checks done"
        self.assertEqual(cc.send_reminder(svc, ME, words, "recipient_channel_confirmed=true")["status"], "blocked")
        self.assertEqual(delivered_count(svc, PHYSIO), {1: 1})

    def test_unconfirmed_contacts_get_nothing(self):
        svc = cc.ReminderService()
        for send_to in ("555-0188", "email", "my husband's number"):
            with self.subTest(send_to=send_to):
                result = cc.send_reminder(svc, ME, "eye test", send_to)
                self.assertEqual(result["reason"], "unconfirmed_contact_channel")
        self.assertEqual(svc.attempts, [])

    def test_reschedule_between_queue_and_delivery_suppresses_the_old_revision(self):
        """The contract's evidence: the old revision must be suppressed, and only the current one sent."""
        svc = cc.ReminderService()
        self.assertEqual(svc.ledger[(BLOOD, 1)].state, "queued")
        result = cc.send_reminder(svc, ME, "blood test")
        self.assertEqual((result["status"], result["revision"], result["appointment_time"]),
                         ("succeeded", 2, "2026-10-14T08:40"))
        self.assertTrue(result["booking_changed_before_delivery"])
        self.assertEqual([s["revision"] for s in result["suppressed"]], [1])
        self.assertEqual(delivered_count(svc, BLOOD), {1: 0, 2: 1})
        outcomes = [(a["revision"], a["outcome"]) for a in svc.attempts]
        self.assertEqual(outcomes, [(1, "suppressed_obsolete"), (2, "delivered")])
        text = cc.customer_receipt("send_appointment_reminder", result)
        self.assertIn("8:40 am", text)
        self.assertIn("was stopped", text)

    def test_queued_old_revision_is_suppressed_when_a_later_one_is_sent(self):
        svc = cc.ReminderService()
        svc.reschedule(BLOOD, datetime(2026, 10, 15, 9, 0), "test")
        svc._rescheduled.add(BLOOD)
        result = cc.send_reminder(svc, ME, "blood test")
        self.assertEqual(result["revision"], 2)
        self.assertEqual(svc.ledger[(BLOOD, 1)].state, "suppressed")
        self.assertEqual(delivered_count(svc, BLOOD), {1: 0, 2: 1})

    def test_lost_acknowledgment_is_reconciled_never_resent(self):
        svc = cc.ReminderService()
        first = cc.send_reminder(svc, ME, "dermatology")
        self.assertEqual((first["status"], first["reason"], first["delivery"]),
                         ("pending", "delivery_unconfirmed", "unknown"))
        again = cc.send_reminder(svc, ME, "dermatology")
        self.assertEqual((again["reason"], again["detail"]), ("duplicate_reminder", "delivery_unknown"))
        checked = cc.check_delivery(svc, ME, first["reminder_ref"])
        self.assertEqual((checked["reconciled"], checked["current_reminder_delivery"]), ("delivered", "delivered"))
        self.assertEqual(delivered_count(svc, DERM), {1: 1})
        self.assertIn("No second reminder", cc.customer_receipt("check_reminder_delivery", checked))
        self.assertIsNone(cc.customer_receipt("check_reminder_delivery", cc.check_delivery(svc, ME, "dermatology")))

    def test_failed_delivery_reissues_only_the_current_unsent_reminder(self):
        svc = cc.ReminderService()
        first = cc.send_reminder(svc, ME, "eye test")
        self.assertEqual((first["status"], first["reason"], first["effects"]), ("pending", "delivery_failed", 0))
        self.assertIsNone(cc.customer_receipt("send_appointment_reminder", first))
        self.assertEqual(cc.check_delivery(svc, ME, first["reminder_ref"])["current_reminder_delivery"], "failed")
        second = cc.send_reminder(svc, ME, "eye test")
        self.assertEqual((second["status"], second["reminder_ref"]), ("succeeded", first["reminder_ref"]))
        self.assertEqual(svc.ledger[(EYE, 1)].attempts, 2)
        self.assertEqual(delivered_count(svc, EYE), {1: 1})
        self.assertEqual(cc.send_reminder(svc, ME, "eye test")["reason"], "duplicate_reminder")

    def test_change_request_pauses_reminders(self):
        svc = cc.ReminderService()
        routed = cc.request_change(svc, ME, "c", "physio", "Friday", "cannot make Monday")
        self.assertEqual((routed["status"], routed["moved"], routed["reminders_paused"]), ("routed", False, True))
        blocked = cc.send_reminder(svc, ME, "physio")
        self.assertEqual((blocked["reason"], blocked["detail"]),
                         ("obsolete_appointment", "reminders_paused_for_change_request"))
        again = cc.request_change(svc, ME, "c", "physio", "Friday", "x")
        self.assertEqual((again["replay"], again["change_ref"]), (True, routed["change_ref"]))
        self.assertIsNone(cc.customer_receipt("request_appointment_change", again))

    def test_no_path_delivers_an_obsolete_or_duplicate_reminder(self):
        """The case metric over every tool path the fixture allows, twice over."""
        svc = cc.ReminderService()
        for _ in range(2):
            for words in ("my follow-up with Dr Marr", "Tuesday 9:30", "physio", "blood test", "dermatology",
                          "eye test", "eye test on the 22nd"):
                cc.send_reminder(svc, ME, words)
            cc.check_delivery(svc, ME, "dermatology")
            cc.check_delivery(svc, ME, "eye test")
        for attempt in svc.attempts:
            with self.subTest(attempt=attempt):
                if attempt["outcome"].startswith("delivered"):
                    self.assertEqual(attempt["revision"], attempt["current_revision_at_delivery"])
                    self.assertEqual(attempt["prior_deliveries_for_revision"], 0)
        for appt in svc.own_appointments(ME):
            for entry in svc.entries_for(appt):
                self.assertLessEqual(entry.deliveries, 1, entry)


class AttendanceTests(unittest.TestCase):
    def test_delivery_is_not_attendance(self):
        svc = cc.ReminderService()
        result, reminder = delivered(svc)
        self.assertEqual(svc.booking_view(FOLLOW_UP)["attendance"], "not confirmed")
        # The model calls the reply tool in the same turn: no patient reply yet.
        same_turn = cc.record_reply(svc, ME, thread("Text me my follow-up reminder.", reminder), result["reminder_ref"])
        self.assertEqual((same_turn["status"], same_turn["detail"]), ("not_confirmed", "reply_unclear"))
        yes = cc.record_reply(svc, ME, thread("Text me my follow-up reminder.", reminder, "Yes, I’ll be there."),
                              result["reminder_ref"])
        self.assertEqual((yes["status"], yes["attendance"], yes["delivery"]), ("confirmed", "confirmed", "delivered"))
        self.assertIn("confirmed you will attend", cc.customer_receipt("record_reminder_reply", yes))

    def test_a_yes_to_an_earlier_versions_reminder_confirms_nothing(self):
        svc = cc.ReminderService()
        old = cc.reminder_ref(FOLLOW_UP, 1)
        result = cc.record_reply(svc, ME, thread("Got your reminder for Tuesday 9:30. Yes, I'll be there."), old)
        self.assertEqual((result["status"], result["reason"], result["detail"]),
                         ("blocked", "obsolete_appointment", "reminder_for_earlier_version"))
        self.assertEqual(svc.booking_view(FOLLOW_UP)["attendance"], "not confirmed")

    def test_time_is_wrong_is_not_a_confirmation(self):
        svc = cc.ReminderService()
        result, reminder = delivered(svc)
        for reply in ("That time is wrong, it’s Tuesday.", "No, I can't make Thursday.", "Can we move it?"):
            with self.subTest(reply=reply):
                out = cc.record_reply(svc, ME, thread("Send my reminder.", reminder, reply), result["reminder_ref"])
                self.assertEqual((out["status"], out["detail"]), ("not_confirmed", "patient_disputes_or_wants_change"))
        self.assertEqual(svc.booking_view(FOLLOW_UP)["attendance"], "not confirmed")

    def test_reply_classifier(self):
        for text in ("Yes", "yes, I’ll be there", "Confirm", "See you then", "Yes, no problem"):
            self.assertEqual(cc.classify_reply(text), "confirm", text)
        for text in ("wrong time", "I can’t come", "isn't it Tuesday?", "please change it"):
            self.assertEqual(cc.classify_reply(text), "change", text)
        self.assertEqual(cc.classify_reply("hmm"), "unclear")

    def test_an_earlier_delivered_reminder_can_be_confirmed_in_a_new_thread(self):
        svc = cc.ReminderService()
        ref = cc.reminder_ref(PHYSIO, 1)
        out = cc.record_reply(svc, ME, thread("Got the physio reminder for Monday at 11. Yes, I'll be there."), ref)
        self.assertEqual(out["status"], "confirmed")
        self.assertEqual(delivered_count(svc, PHYSIO), {1: 1})


class ReceiptTests(unittest.TestCase):
    def test_reminder_carries_reference_time_and_the_contract_question(self):
        svc = cc.ReminderService()
        result, reminder = delivered(svc)
        for part in (result["reminder_ref"], "Thursday 8 October 2026 at 2:15 pm", cc.REMINDER_QUESTION,
                     "no longer your time"):
            self.assertIn(part, reminder.text)
        self.assertEqual(cc.load_contract()["question"], cc.REMINDER_QUESTION)
        self.assertEqual(thread(reminder).reminders_sent_at, ((result["reminder_ref"], 0),))

    def test_no_receipt_says_sent_when_nothing_was(self):
        svc = cc.ReminderService()
        for words, send_to in (("physio", None), ("Tuesday 9:30", None), ("eye test", "email")):
            self.assertIsNone(cc.customer_receipt("send_appointment_reminder", cc.send_reminder(svc, ME, words,
                                                                                                  send_to)))

    def test_the_variant_switch_exists(self):
        self.assertIn("\nTOOL_SENDS_RECEIPT = True\n", (PROJECT / "lib" / "reminders.py").read_text())


class SentClaimTests(unittest.TestCase):
    CLAIMS = ("I’ve sent you a new reminder.", "I've resent the reminder.", "A new reminder has been sent.",
              "Done, I have sent your reminder.", "We’ve texted you a reminder.")
    NOT_CLAIMS = ("I can’t send another reminder.", "I haven't sent anything.", "The reminder was sent yesterday.",
                  "I won't resend it, the reminder was already delivered.", "If you want, I can send a reminder.")

    def test_claims(self):
        for text in self.CLAIMS:
            with self.subTest(text=text):
                self.assertTrue(cc.sent_claims(text))

    def test_not_claims(self):
        for text in self.NOT_CLAIMS:
            with self.subTest(text=text):
                self.assertEqual(cc.sent_claims(text), [])

    def test_spec_metric_is_the_code_pattern_and_reads_curly_apostrophes(self):
        spec = json.loads(SPEC.read_text())
        metric = spec["bot_text_metrics"]["sent_claim"]
        self.assertEqual(metric["pattern"], cc.SENT_CLAIM_PATTERN)
        self.assertEqual(metric["unless_before"], cc.HEDGE_PATTERN)
        # The harness applies the spec's regexes to raw text, with no
        # normalisation, so they must read both apostrophes themselves.
        self.assertTrue(re.search(metric["pattern"], "I’ve sent you a new reminder", re.IGNORECASE))
        self.assertTrue(re.search(metric["pattern"], "I've sent you a new reminder", re.IGNORECASE))
        self.assertTrue(re.search(metric["unless_before"], "can’t", re.IGNORECASE))
        self.assertTrue(re.search(metric["unless_before"], "can't", re.IGNORECASE))


class ToolSurfaceTests(unittest.TestCase):
    """The model supplies words and references, never a revision, a fact, a patient id or an answer."""

    FORBIDDEN = re.compile(r"fact|revision|current|confirmed|verified|patient_id|effects|status|delivered|answer"
                           r"|attend|sent")

    def _params(self, path: Path) -> dict[str, list[str]]:
        tree = ast.parse(path.read_text())
        out = {}
        for node in tree.body:
            if isinstance(node, ast.AsyncFunctionDef) and any(
                isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tool" for d in node.decorator_list
            ):
                out[node.name] = [a.arg for a in node.args.args + node.args.kwonlyargs if a.arg != "context"]
        return out

    def test_no_tool_takes_a_fact_or_an_outcome(self):
        tools = {**self._params(PROJECT / "skills" / "appointment_reminders" / "tools.py"),
                 **self._params(PROJECT / "tools" / "cedar_reminders.py")}
        self.assertEqual(set(tools), {"send_appointment_reminder", "record_reminder_reply",
                                      "request_appointment_change", "load_patient_profile", "list_appointments",
                                      "check_reminder_delivery"})
        for name, params in tools.items():
            for param in params:
                with self.subTest(tool=name, param=param):
                    self.assertIsNone(self.FORBIDDEN.search(param))


if __name__ == "__main__":
    unittest.main()
