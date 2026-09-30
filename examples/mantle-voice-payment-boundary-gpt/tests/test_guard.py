"""Offline checks for the Willow Shop payment boundary. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import payments as wp  # noqa: E402
from lib import pci  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "voice-payment-boundary.json"
)
DANA = "WS-CUST-5521"
CARD = "4111111111111111"


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), wp.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = wp.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(wp.lab_outcome(variant["facts"], contract),
                                 (expected["status"], expected["reason"], expected["effects"]))

    def test_rule_phases(self):
        self.assertEqual([r["field"] for r in wp.rules("request")], ["secure_channel_selected", "recorder_excluded"])
        self.assertEqual([r["field"] for r in wp.rules("receipt")], ["processor_receipt_verified"])


class OrganisationGuardTests(unittest.TestCase):
    def test_fixture_is_the_casebook_organisation(self):
        self.assertEqual(wp.ORGANISATION, "Willow Shop")
        wp.assert_fictional(wp.load_data(), wp.load_contract())

    def test_unmarked_organisation_is_refused(self):
        data = wp.load_data()
        data["organisation"] = "Willow Shop"
        with self.assertRaises(wp.FictionalOrganisationError):
            wp.assert_fictional(data, wp.load_contract())

    def test_any_other_organisation_is_refused_even_when_marked(self):
        data = wp.load_data()
        data["organisation"] = "Harbourline Stores (fictional)"
        with self.assertRaises(wp.FictionalOrganisationError):
            wp.assert_fictional(data, wp.load_contract())

    def test_unmarked_processor_is_refused(self):
        data = wp.load_data()
        data["processor"] = "Quillfeather Payments"
        with self.assertRaises(wp.FictionalOrganisationError):
            wp.assert_fictional(data, wp.load_contract())

    def test_customer_contacts_must_be_reserved(self):
        for field, value in (("email", "dana.whitlock@example.org"), ("mobile", "+1 614 555 2368")):
            data = wp.load_data()
            data["customers"][DANA][field] = value
            with self.subTest(field=field), self.assertRaises(wp.FictionalOrganisationError):
                wp.assert_fictional(data, wp.load_contract())

    def test_contract_must_be_the_synthetic_fixture(self):
        contract = wp.load_contract()
        contract["provenance"]["kind"] = "production-policy"
        with self.assertRaises(wp.FictionalOrganisationError):
            wp.assert_fictional(wp.load_data(), contract)


class RedactionTests(unittest.TestCase):
    def assertRemoved(self, text, continuation=False):
        out, n = pci.redact(text, continuation=continuation)
        self.assertGreater(n, 0, text)
        self.assertNotIn(CARD[:8], pci.digits_only(out))
        self.assertIn(pci.PLACEHOLDER, out)
        return out

    def assertKept(self, text, continuation=False):
        self.assertEqual(pci.redact(text, continuation=continuation), (text, 0))

    def test_card_number_as_digits_words_and_mixed(self):
        for text in ("4111 1111 1111 1111", "4111-1111-1111-1111", "four one one one, one one one one, "
                     "one one one one, one one one one", "It's 4111, one one one one, 1111 1111",
                     "forty one eleven eleven eleven eleven eleven eleven eleven",
                     "4 1 1 1 um 1 1 1 1 1 1 1 1 1 1 1 1"):
            with self.subTest(text=text):
                self.assertRemoved(text)

    def test_security_code_and_expiry_after_a_cue(self):
        out = self.assertRemoved("the card expires oh four twenty nine and the security code is seven three one")
        self.assertEqual(out.count(pci.PLACEHOLDER), 2)
        self.assertRemoved("CVV 731")
        self.assertRemoved("the three digits on the back are 7 3 1")

    def test_straight_and_curly_apostrophes(self):
        for text in ("The card's 5555 5555 5555 4444", "The card’s 5555 5555 5555 4444",
                     "The card's number is 4 1 1", "The card’s number is 4 1 1", "card’s 731"):
            with self.subTest(text=text):
                self.assertRemoved(text)

    def test_card_read_in_two_breaths(self):
        self.assertRemoved("Card number four one one one, one one one one.")
        self.assertRemoved("One one one one. Did you get that?", continuation=True)
        self.assertRemoved("and 1111", continuation=True)

    def test_what_the_agent_needs_is_kept(self):
        for text in ("My order is W S one zero five one seven.", "order WS-10517 please",
                     "I paid, my confirmation number is 77120", "It's 149 dollars", "Yes.",
                     "Email me the payment link for order W S one zero five two eight.",
                     "I've paid it on my phone.", "Oh, okay, text me.", "the one on file"):
            with self.subTest(text=text):
                self.assertKept(text)
        self.assertKept("Email me the link for order W S one zero five two eight.", continuation=True)

    def test_digits_only_reads_number_words(self):
        self.assertEqual(pci.digits_only("W S one zero five one seven"), "10517")
        self.assertEqual(pci.digits_only("double four seven one"), "4471")


class ToolLogicTests(unittest.TestCase):
    def setUp(self):
        self.service = wp.PaymentService("test")

    def prepare(self, order="WS-10517", channel="text", texts=(), redaction=True):
        return wp.prepare_secure_payment(self.service, DANA, list(texts), redaction, order, channel)

    def test_approved_channels_only(self):
        for channel, status in (("text", "ready"), ("SMS", "ready"), ("email", "ready"), ("e-mail", "ready"),
                                ("phone", "blocked"), ("voice", "blocked"), ("read card over the call", "blocked"),
                                ("", "blocked")):
            with self.subTest(channel=channel):
                result, memory = self.prepare(channel=channel)
                self.assertEqual(result["status"], status)
                if status == "blocked":
                    self.assertEqual(result["reason"], "unsafe_capture_channel")
                    self.assertEqual(memory, {})

    def test_card_digits_in_an_argument_are_refused_and_not_echoed(self):
        result, memory = self.prepare(order="4111 1111 1111 1111")
        self.assertEqual((result["status"], result["reason"]), ("blocked", "unsafe_capture_channel"))
        self.assertNotIn(CARD, pci.digits_only(json.dumps(result)))
        result, _ = self.prepare(channel="text 4111111111111111")
        self.assertEqual(result["reason"], "unsafe_capture_channel")
        self.assertNotIn(CARD, json.dumps(result))

    def test_recorder_not_excluded_without_redaction_or_with_card_in_record(self):
        result, _ = self.prepare(redaction=False)
        self.assertEqual((result["status"], result["reason"]), ("blocked", "recording_not_excluded"))
        result, _ = self.prepare(texts=["my card number is 4111 1111 1111 1111"])
        self.assertEqual((result["status"], result["reason"]), ("blocked", "recording_not_excluded"))
        result, _ = self.prepare(texts=["my card number is " + pci.PLACEHOLDER])
        self.assertEqual(result["status"], "ready")

    def test_link_then_verified_receipt_in_a_later_turn(self):
        result, memory = self.prepare()
        sent = wp.send_secure_payment_link(self.service, DANA, [], True, memory, "WS-10517", user_turn=2)
        self.assertEqual((sent["status"], sent["payment_status"], sent["effects"]), ("link_sent", "pending", 1))
        same_turn = wp.check_payment_status(self.service, DANA, "WS-10517", user_turn=2)
        self.assertEqual((same_turn["status"], same_turn["reason"]), ("pending", "awaiting_customer"))
        paid = wp.check_payment_status(self.service, DANA, "WS-10517", user_turn=3)
        self.assertEqual((paid["status"], paid["reason"], paid["payment_status"]),
                         ("succeeded", "verified_fixture_receipt", "paid"))
        self.assertRegex(paid["processor_reference"], r"^QP-\d{6}$")

    def test_send_needs_the_prepared_order(self):
        _, memory = self.prepare(order="WS-10517")
        result = wp.send_secure_payment_link(self.service, DANA, [], True, memory, "WS-10528", user_turn=1)
        self.assertEqual(result["status"], "blocked")
        result = wp.send_secure_payment_link(self.service, DANA, [], True, {}, "WS-10517", user_turn=1)
        self.assertEqual(result["detail"], "not_prepared")

    def test_send_rechecks_the_record(self):
        _, memory = self.prepare()
        result = wp.send_secure_payment_link(self.service, DANA, ["it's 4111 1111 1111 1111"], True, memory,
                                             "WS-10517", user_turn=2)
        self.assertEqual(result["reason"], "recording_not_excluded")

    def test_unverified_receipt_stays_pending(self):
        _, memory = self.prepare(order="WS-10563", channel="email")
        wp.send_secure_payment_link(self.service, DANA, [], True, memory, "WS-10563", user_turn=1)
        result = wp.check_payment_status(self.service, DANA, "WS-10563", user_turn=2)
        self.assertEqual((result["status"], result["reason"], result["effects"]),
                         ("pending", "unverified_processor_receipt", 1))
        self.assertNotIn("processor_reference", result)

    def test_expired_link_then_new_link_pays(self):
        _, memory = self.prepare(order="WS-10546")
        wp.send_secure_payment_link(self.service, DANA, [], True, memory, "WS-10546", user_turn=1)
        self.assertEqual(wp.check_payment_status(self.service, DANA, "WS-10546", user_turn=2)["status"], "expired")
        _, memory = self.prepare(order="WS-10546")
        wp.send_secure_payment_link(self.service, DANA, [], True, memory, "WS-10546", user_turn=3)
        self.assertEqual(wp.check_payment_status(self.service, DANA, "WS-10546", user_turn=4)["status"], "succeeded")

    def test_no_secure_channel_cancels_collection(self):
        result, memory = self.prepare(order="WS-10581")
        self.assertEqual((result["status"], result["reason"]), ("cancelled", "secure_channel_unavailable"))
        self.assertIn(wp.APPROVED_ALTERNATIVE, result["next_step"])
        self.assertEqual(memory, {})

    def test_callers_word_is_not_a_receipt(self):
        result = wp.check_payment_status(self.service, DANA, "WS-10517", user_turn=1)
        self.assertEqual((result["status"], result["reason"]), ("pending", "no_payment_session"))

    def test_other_customers_order_is_not_found(self):
        result, _ = self.prepare(order="WS-10610")
        self.assertEqual(result["status"], "not_found")
        self.assertNotIn("Ostrander", json.dumps(result))

    def test_nothing_owed(self):
        self.assertEqual(wp.look_up_order_balance(self.service, DANA, "WS-10592")["status"], "paid_in_full")
        self.assertEqual(self.prepare(order="WS-10592")[0]["status"], "nothing_owed")

    def test_declined_secure_step_leaves_it_pending(self):
        result = wp.leave_payment_pending(self.service, DANA, "WS-10517")
        self.assertEqual((result["status"], result["payment_status"]), ("pending", "unpaid"))

    def test_forged_receipt_does_not_verify(self):
        receipt = {"reference": "QP-000001", "order": "WS-10517", "amount_cents": 14900, "status": "captured",
                   "signature": "0" * 64}
        self.assertFalse(wp.verify_receipt(receipt, "WS-10517", 14900))


class MemoryAndReceiptTests(unittest.TestCase):
    def test_every_memory_value_is_under_100_characters(self):
        data = wp.load_data()
        for order, record in data["orders"].items():
            customer = data["customers"][record["customer_id"]]
            for channel in wp.APPROVED_CHANNELS:
                for key, value in wp.memory_values(order, channel, record["balance_cents"], customer).items():
                    with self.subTest(order=order, channel=channel, key=key):
                        self.assertLess(len(value), wp.MEMORY_VALUE_LIMIT)
                        self.assertFalse(pci.contains_payment_secret(value))

    def test_memory_keys_match_the_skill_schema(self):
        schema = (PROJECT / "skills" / "pay_order_balance" / "memory.yml").read_text()
        self.assertEqual(sorted(re.findall(r"^    (\w+):$", schema, re.M)), sorted(wp.MEMORY_KEYS))

    def test_receipts_hold_no_card_data_and_name_the_reference(self):
        service = wp.PaymentService("receipts")
        _, memory = wp.prepare_secure_payment(service, DANA, [], True, "WS-10517", "text")
        sent = wp.send_secure_payment_link(service, DANA, [], True, memory, "WS-10517", user_turn=1)
        paid = wp.check_payment_status(service, DANA, "WS-10517", user_turn=2)
        texts = [wp.customer_receipt("send_secure_payment_link", sent),
                 wp.customer_receipt("check_payment_status", paid),
                 wp.customer_receipt("leave_payment_pending", wp.leave_payment_pending(service, DANA, "WS-10528"))]
        for text in texts:
            self.assertTrue(text)
            self.assertFalse(pci.contains_payment_secret(text))
        self.assertIn(wp.spoken_reference(paid["processor_reference"]), texts[1])
        self.assertIn("pending", texts[0])

    def test_no_receipt_for_a_block(self):
        self.assertIsNone(wp.customer_receipt("send_secure_payment_link", {"status": "blocked"}))

    def test_spoken_labels(self):
        self.assertEqual(wp.spoken_order("WS-10517"), "W S, 1 0 5 1 7")
        self.assertEqual(wp.spoken_reference("QP-482913"), "Q P, 4 8 2, 9 1 3")
        self.assertEqual(wp.spoken_amount(6250), "62 dollars and 50 cents")


class ProjectShapeTests(unittest.TestCase):
    def test_no_tool_takes_card_details(self):
        source = (PROJECT / "skills" / "pay_order_balance" / "tools.py").read_text()
        params = re.findall(r"async def \w+\(([^)]*)\)", source)
        for signature in params:
            self.assertNotRegex(signature.lower(), r"card|cvv|cvc|expir|security|pan\b")

    def test_no_denial_utterance(self):
        skill = (PROJECT / "skills" / "pay_order_balance" / "skill.md").read_text()
        self.assertNotIn("utter_on_user_denial", skill)

    def test_voice_tool_timeout_covers_spoken_receipts(self):
        self.assertRegex((PROJECT / "agent.yml").read_text(), r"(?m)^tool_timeout: 30$")

    def test_voice_channel_uses_the_redacting_engine(self):
        text = (PROJECT / "integrations.yml").read_text()
        self.assertEqual(text.count("name: engines.deepgram_pci.DeepgramRedactingCardDetails"), 2)


if __name__ == "__main__":
    unittest.main()
