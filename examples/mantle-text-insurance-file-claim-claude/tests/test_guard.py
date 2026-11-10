"""Offline checks for the HarborCover claim-intake guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import itertools
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import claims as hc  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "insurance-file-claim.json"
)
ME = hc.SESSION_CUSTOMER_ID
HOME, AUTO, LANDLORD, OTHERS = "HC-HO-552104", "HC-AU-778210", "HC-RD-330915", "HC-HO-610233"


class UserUttered:  # stand-ins named like Rasa's events
    def __init__(self, text, metadata=None):
        self.text, self.metadata = text, metadata or {}


class BotUttered:
    def __init__(self, text, metadata=None):
        self.text, self.metadata = text, metadata or {}


def convo(*messages: str, question: str | None = None, answered: bool = True) -> hc.Conversation:
    users = tuple(hc.UserMessage(m, hc.attachments_in(m)) for m in messages)
    return hc.Conversation(users, question, answered if question else False)


def question_for(service: hc.ClaimsIntake, draft: hc.Draft) -> str:
    values = hc.memory_values(service, draft)
    template = (PROJECT / "skills" / "file_claim" / "responses.yml").read_text()
    text = " ".join(template.split("- text: >", 1)[1].split())
    return re.sub(r"\{(\w+)\}", lambda m: values[m.group(1)], text)


def drafted(service, messages, policy=HOME, loss_type="water_damage", loss_date="2026-09-26",
            summary="Pipe leaked and brought down the kitchen ceiling"):
    result, draft = hc.start_claim_draft(service, ME, "conv-1", convo(*messages), policy, loss_type, loss_date,
                                         summary, "details", None)
    assert result["status"] == "drafted", result
    return draft


def confirmed(service, draft, messages, reply="Yes, that's accurate."):
    """The conversation after the engine read this draft back and the customer answered."""
    return convo(*messages, reply, question=question_for(service, draft))


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), hc.load_contract(),
                         "lib/fixtures/case-contract.json has drifted from the casebook lab")

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """The guard reproduces all ten authored variants: false, missing, string."""
        contract = hc.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                facts, expected = variant["facts"], variant["expected"]
                request = hc.evaluate(facts, "request", contract)
                if request:
                    self.assertEqual((expected["status"], request), ("blocked", expected["reason"]))
                    continue
                receipt = hc.evaluate(facts, "receipt", contract)
                self.assertEqual("pending" if receipt else "succeeded", expected["status"])
                self.assertEqual(receipt or "verified_fixture_receipt", expected["reason"])


class FictionalOrganisationTests(unittest.TestCase):
    def test_fixture_is_the_casebooks_fictional_insurer(self):
        hc.assert_fictional(hc.load_data(), hc.load_contract())
        self.assertEqual(hc.ORGANISATION, hc.load_contract()["organisation"])
        self.assertEqual(hc.allowed_organisations(hc.load_contract()), frozenset({"HarborCover"}))

    def test_any_other_organisation_is_refused_even_when_marked_fictional(self):
        data = hc.load_data()
        data["organisation"] = "Keystone Mutual (fictional insurer)"
        with self.assertRaises(hc.FictionalOrganisationError):
            hc.assert_fictional(data, hc.load_contract())

    def test_nested_organisation_fields_are_checked(self):
        data = hc.load_data()
        data["policies"][HOME]["insurer"] = "Keystone Mutual (fictional insurer)"
        with self.assertRaises(hc.FictionalOrganisationError):
            hc.assert_fictional(data, hc.load_contract())
        data["policies"][HOME]["insurer"] = "HarborCover (fictional insurer)"
        hc.assert_fictional(data, hc.load_contract())

    def test_unmarked_or_undeclared_data_is_refused(self):
        for key, value in (("organisation", "HarborCover"), ("note", "Sample data.")):
            data = hc.load_data()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(hc.FictionalOrganisationError):
                hc.assert_fictional(data, hc.load_contract())


class MemoryLimitTests(unittest.TestCase):
    """Mantle cuts a memory value at 100 characters in the prompt, silently."""

    def test_project_memory_values_fit(self):
        profile = hc.session_profile()
        for key in ("customer_id", "first_name", "policy_list"):
            self.assertLessEqual(len(profile[key]), hc.MEMORY_VALUE_LIMIT, key)

    def test_every_draft_memory_value_fits_for_every_fixture_combination(self):
        data = hc.load_data()
        uploads = data["uploads"]
        longest = "x" * hc.LOSS_SUMMARY_LIMIT
        checked = 0
        for number, policy in data["policies"].items():
            if policy["customer_id"] != ME:
                continue
            for key, loss in data["loss_types"].items():
                if policy["line"] not in loss["lines"]:
                    continue
                relevant = [n for n, u in uploads.items() if u["satisfies"] in loss["required"]] + ["unknown-file.pdf"]
                for size in range(len(relevant) + 1):
                    for files in itertools.combinations(relevant, size):
                        messages = [f"[attached: {', '.join(files)}]"] if files else ["no files"]
                        for extra_turns in (0, 1):
                            service = hc.ClaimsIntake()
                            convo_ = convo(*messages, *(["later"] * extra_turns))
                            result, draft = hc.start_claim_draft(service, ME, "c", convo_, number, key,
                                                                 "2026-09-01", longest)
                            self.assertEqual(result["status"], "drafted", result)
                            for name, value in hc.memory_values(service, draft).items():
                                self.assertLessEqual(len(value), hc.MEMORY_VALUE_LIMIT, (name, value))
                            checked += 1
        self.assertGreater(checked, 1000)

    def test_a_long_summary_is_refused_not_cut(self):
        service = hc.ClaimsIntake()
        result, draft = hc.start_claim_draft(service, ME, "c", convo("x"), HOME, "water_damage", "2026-09-26",
                                             "y" * (hc.LOSS_SUMMARY_LIMIT + 1))
        self.assertEqual((result["status"], result["reason"]), ("blocked", "loss_summary_too_long"))
        self.assertIsNone(draft)


class DraftTests(unittest.TestCase):
    def test_someone_elses_policy_and_a_missing_one_get_the_same_answer(self):
        service = hc.ClaimsIntake()
        answers = []
        for number in (OTHERS, "HC-HO-999999"):
            result, _ = hc.start_claim_draft(service, ME, "c", convo("x"), number, "water_damage", "2026-09-26", "s")
            answers.append({k: v for k, v in result.items() if k != "policy_number_given"})
        self.assertEqual(answers[0], answers[1])
        self.assertEqual(answers[0]["status"], "not_found")

    def test_policy_by_digits_and_loss_type_by_words(self):
        service = hc.ClaimsIntake()
        result, _ = hc.start_claim_draft(service, ME, "c", convo("x"), "552104", "burst pipe", "26 September", "s")
        self.assertEqual((result["policy_number"], result["loss_type"], result["loss_date"]),
                         (HOME, "water damage", "2026-09-26"))
        result, _ = hc.start_claim_draft(service, ME, "c", convo("x"), AUTO, "water_damage", "2026-09-26", "s")
        self.assertEqual(result["reason"], "loss_type_not_identified")

    def test_future_date_is_refused(self):
        service = hc.ClaimsIntake()
        result, _ = hc.start_claim_draft(service, ME, "c", convo("x"), HOME, "water_damage", "2026-10-02", "s")
        self.assertEqual(result["reason"], "loss_date_in_future")

    def test_a_draft_is_not_filed(self):
        service = hc.ClaimsIntake()
        result, _ = hc.start_claim_draft(service, ME, "c", convo("x"), HOME, "water_damage", "2026-09-26", "s")
        self.assertIs(result["filed"], False)
        self.assertNotIn("claim_intake_reference", result)


class AttachmentTests(unittest.TestCase):
    def test_received_failed_and_not_provided_are_known(self):
        service = hc.ClaimsIntake()
        msgs = ["Storm took the fence down. [attached: fence-down.jpg, fence-quote.pdf]"]
        draft = drafted(service, msgs, loss_type="storm_damage")
        view = hc.check_attachments(service, ME, convo(*msgs), draft.draft_id)[0]
        self.assertTrue(view["required_attachment_state_known"])
        self.assertEqual(view["material_received"], [{"requirement": "photos of the damage", "files": ["fence-down.jpg"]}])
        self.assertEqual(view["follow_up_required"], [{"requirement": "repair estimate or invoice", "why": "upload failed"}])
        self.assertEqual(hc.memory_values(service, draft)["claim_ready_to_submit"], "yes")

    def test_a_file_the_customer_only_mentions_is_not_received(self):
        service = hc.ClaimsIntake()
        msgs = ["I sent you the photos and the invoice already."]
        draft = drafted(service, msgs)
        self.assertEqual([f["why"] for f in hc.follow_up_required(draft.material)], ["not provided", "not provided"])

    def test_scanning_blocks_until_the_next_customer_message(self):
        service = hc.ClaimsIntake()
        msgs = ["My bike was stolen. [attached: bike-receipt.pdf, police-report.pdf]"]
        draft = drafted(service, msgs, loss_type="theft")
        self.assertFalse(draft.material["required_attachment_state_known"])
        self.assertEqual(hc.memory_values(service, draft)["claim_ready_to_submit"], "")
        later = [*msgs, "Can you check it again?"]
        view = hc.check_attachments(service, ME, convo(*later), draft.draft_id)[0]
        self.assertTrue(view["required_attachment_state_known"])
        self.assertEqual(view["draft_version"], 2)

    def test_a_stuck_file_can_be_left_out_and_is_then_still_needed(self):
        service = hc.ClaimsIntake()
        msgs = ["Branch cracked the window. [attached: window-crack.jpg, glazier-quote.pdf]"]
        draft = drafted(service, msgs, loss_type="accidental_damage")
        stuck = hc.check_attachments(service, ME, convo(*msgs, "check again"), draft.draft_id)[0]
        self.assertFalse(stuck["required_attachment_state_known"])
        left_out = hc.check_attachments(service, ME, convo(*msgs, "leave the quote out"), draft.draft_id,
                                        ["glazier-quote.pdf"])[0]
        self.assertTrue(left_out["required_attachment_state_known"])
        self.assertEqual(left_out["follow_up_required"], [{"requirement": "repair estimate or invoice", "why": "not provided"}])

    def test_teams_attachments_in_metadata_are_read(self):
        events = [UserUttered("Here are the photos", {"attachments": [{"name": "bumper-1.jpg", "contentType": "image/jpeg"}]})]
        self.assertEqual(conversation_from_events(events).user_messages[0].attachments, ("bumper-1.jpg",))


class SubmissionTests(unittest.TestCase):
    MSGS = ["Pipe leak on 26 September. [attached: leak-ceiling-1.jpg, plumber-invoice.pdf]"]

    def test_confirmed_report_is_filed_with_its_material(self):
        service = hc.ClaimsIntake()
        draft = drafted(service, self.MSGS)
        result = hc.submit_claim_report(service, ME, hc.memory_values(service, draft),
                                        confirmed(service, draft, self.MSGS), draft.draft_id)
        self.assertEqual((result["status"], result["effects"]), ("succeeded", 1))
        self.assertRegex(result["claim_intake_reference"], r"^HC-CLI-\d{5}$")
        self.assertEqual(result["follow_up_required"], [])
        self.assertIsNone(result["coverage_decision"])

    def test_without_the_read_back_nothing_is_filed(self):
        service = hc.ClaimsIntake()
        draft = drafted(service, self.MSGS)
        memory = hc.memory_values(service, draft)
        for conversation in (convo(*self.MSGS, "Just file it."),
                             convo(*self.MSGS, question=question_for(service, draft), answered=False)):
            result = hc.submit_claim_report(service, ME, memory, conversation, draft.draft_id)
            self.assertEqual((result["status"], result["reason"], result["effects"]),
                             ("blocked", "unconfirmed_report", 0))

    def test_a_corrected_date_needs_a_new_read_back(self):
        service = hc.ClaimsIntake()
        draft = drafted(service, self.MSGS)
        old_question = question_for(service, draft)
        update, _ = hc.update_claim_draft(service, ME, convo(*self.MSGS), draft.draft_id, loss_date="2026-09-25")
        self.assertEqual((update["status"], update["changed"], update["draft_version"]), ("updated", ["loss_date"], 2))
        stale = convo(*self.MSGS, "Actually it was the 25th", question=old_question)
        result = hc.submit_claim_report(service, ME, hc.memory_values(service, draft), stale, draft.draft_id)
        self.assertEqual(result["reason"], "unconfirmed_report")
        fresh = confirmed(service, draft, self.MSGS)
        result = hc.submit_claim_report(service, ME, hc.memory_values(service, draft), fresh, draft.draft_id)
        self.assertEqual((result["status"], result["loss_date"]), ("succeeded", "2026-09-25"))

    def test_a_scanning_file_blocks_submission(self):
        service = hc.ClaimsIntake()
        msgs = ["Window. [attached: window-crack.jpg, glazier-quote.pdf]"]
        draft = drafted(service, msgs, loss_type="accidental_damage")
        result = hc.submit_claim_report(service, ME, hc.memory_values(service, draft),
                                        confirmed(service, draft, msgs), draft.draft_id)
        self.assertEqual(result["status"], "blocked")
        self.assertIn(result["reason"], ("attachment_state_unknown", "unconfirmed_report"))
        self.assertEqual(service.submissions, {})

    def test_submitting_again_replays_and_files_nothing_twice(self):
        service = hc.ClaimsIntake()
        draft = drafted(service, self.MSGS)
        conversation = confirmed(service, draft, self.MSGS)
        memory = hc.memory_values(service, draft)
        first = hc.submit_claim_report(service, ME, memory, conversation, draft.draft_id)
        again = hc.submit_claim_report(service, ME, memory, conversation, draft.draft_id)
        self.assertEqual(again["claim_intake_reference"], first["claim_intake_reference"])
        self.assertEqual((again["replay"], again["effects"], len(service.submissions)), (True, 0, 1))

    def test_lost_acknowledgment_is_pending_then_reconciled_to_the_same_claim(self):
        service = hc.ClaimsIntake()
        msgs = ["Someone reversed into my car. [attached: bumper-1.jpg, bodyshop-estimate.pdf]"]
        draft = drafted(service, msgs, policy=AUTO, loss_type="collision")
        pending = hc.submit_claim_report(service, ME, hc.memory_values(service, draft),
                                         confirmed(service, draft, msgs), draft.draft_id)
        self.assertEqual((pending["status"], pending["claim_intake_reference"], pending["filed"]),
                         ("pending", None, False))
        found = hc.check_claim_submission(service, ME, draft.draft_id)
        self.assertEqual((found["status"], found["effects"]), ("acknowledged", 0))
        self.assertEqual(found["claim_intake_reference"], hc.claim_reference(draft.draft_id))

    def test_unavailable_service_is_routed_with_the_draft_kept(self):
        service = hc.ClaimsIntake()
        msgs = ["Water from upstairs at the flat. [attached: tollgate-ceiling.jpg]"]
        draft = drafted(service, msgs, policy=LANDLORD)
        pending = hc.submit_claim_report(service, ME, hc.memory_values(service, draft),
                                         confirmed(service, draft, msgs), draft.draft_id)
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(hc.check_claim_submission(service, ME, draft.draft_id)["status"], "unknown")
        routed = hc.route_claims_intake(service, ME, draft.draft_id, "claims system cannot confirm")
        self.assertEqual((routed["status"], routed["draft_status"], routed["filed"]), ("routed", "retained_pending", False))

    def test_existing_claim_status(self):
        found = hc.check_claim_submission(hc.ClaimsIntake(), ME, "hc-cli-40718")
        self.assertEqual((found["status"], found["coverage_decision"]), ("filed", None))
        self.assertEqual(hc.check_claim_submission(hc.ClaimsIntake(), "HC-CUST-6408", "HC-CLI-40718")["status"],
                         "not_found")


class ReceiptMessageTests(unittest.TestCase):
    def test_the_tool_receipt_carries_the_reference_only_when_filed(self):
        service = hc.ClaimsIntake()
        msgs = SubmissionTests.MSGS
        draft = drafted(service, msgs)
        result = hc.submit_claim_report(service, ME, hc.memory_values(service, draft),
                                        confirmed(service, draft, msgs), draft.draft_id)
        text = hc.customer_receipt("submit_claim_report", result)
        self.assertIn(result["claim_intake_reference"], text)
        self.assertIn("Coverage has not been decided", text)
        blocked = hc.submit_claim_report(service, ME, {}, convo("x"), "HC-FD-00000")
        self.assertIsNone(hc.customer_receipt("submit_claim_report", blocked))

    def test_pending_receipt_says_not_filed(self):
        text = hc.customer_receipt("submit_claim_report", {"status": "pending", "draft_id": "HC-FD-ABCDE"})
        self.assertTrue(text.startswith("Not filed yet"))

    def test_tool_sends_receipt_is_on(self):
        self.assertIs(hc.TOOL_SENDS_RECEIPT, True)


class ConversationTests(unittest.TestCase):
    def test_confirmation_question_and_answer_are_read_from_events(self):
        q = "Here is the report I will submit: ... Draft HC-FD-ABCDE v1. Is that accurate?"
        events = [UserUttered("/session_start"), UserUttered("Leak [attached: a.jpg]"),
                  BotUttered(q, {"utter_action": hc.CONFIRM_UTTER}), UserUttered("Yes.")]
        c = conversation_from_events(events)
        self.assertEqual((c.confirmation_question, c.confirmation_answered), (q, True))
        self.assertEqual([m.text for m in c.user_messages], ["Leak [attached: a.jpg]", "Yes."])
        self.assertFalse(conversation_from_events(events[:3]).confirmation_answered)
        other = conversation_from_events([BotUttered(q, {"utter_action": "utter_greet"}), UserUttered("Yes.")])
        self.assertIsNone(other.confirmation_question)


class FiledClaimMetricTests(unittest.TestCase):
    def spec_metric(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        return spec["bot_text_metrics"]["filed_claim"]

    def test_spec_uses_the_same_pattern(self):
        metric = self.spec_metric()
        self.assertEqual(metric["pattern"], hc.FILED_CLAIM_PATTERN)
        self.assertEqual(metric["unless_before"], hc.FILED_HEDGE_PATTERN)

    def test_pattern_catches_filed_claims_and_skips_hedges(self):
        filed = re.compile(hc.FILED_CLAIM_PATTERN, re.IGNORECASE)
        hedge = re.compile(hc.FILED_HEDGE_PATTERN, re.IGNORECASE)
        for text in ("Your claim has been filed.", "I've submitted your claim.", "Claim filed: HC-CLI-12345."):
            self.assertTrue(filed.search(text), text)
        for text in ("Your claim has not been filed yet.", "Once your claim is filed you'll get a reference."):
            m = filed.search(text)
            self.assertTrue(m is None or hedge.search(text[: m.start()]), text)


if __name__ == "__main__":
    unittest.main()
