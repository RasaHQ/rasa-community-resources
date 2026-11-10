"""Offline checks for the Northgate repayment-plan guard. No model, no network, no licence.

Run from the project directory:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import repayment as rp  # noqa: E402
from lib.conversation import conversation_from_events  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "banking-collections.json"
)
MARISOL = "NG-CUST-7719"


class UserUttered(SimpleNamespace):
    pass


class BotUttered(SimpleNamespace):
    pass


def lab_outcome(facts: dict, contract: dict) -> tuple[str, str]:
    """The lab's execute() order: every rule here is a request rule."""
    reason = rp.evaluate(facts, contract)
    return ("blocked", reason) if reason else ("succeeded", "verified_fixture_receipt")


def convo(*users: str, question: str | None = None, answer: str | None = None) -> rp.Conversation:
    return rp.Conversation(user_texts=tuple(users) + ((answer,) if answer else ()),
                           confirmation_question=question, confirmation_answer=answer)


def question_for(offer_id: str, account: str = "4471") -> str:
    data = rp.load_data()
    acct = data["accounts"][account]
    offer = next(o for o in acct["offers"] if o["offer_id"] == offer_id)
    view = rp._offer_view(offer)
    return (f"Para su {acct['label']}: {view['terms_spoken']}, el primero el {view['first_due_spoken']}. "
            "Elegir un plan no es un pago. ¿Confirma que quiere este plan?")


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(json.loads(CASEBOOK_CONTRACT.read_text()), rp.load_contract())

    def test_every_lab_variant_gets_the_lab_outcome(self):
        contract = rp.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                expected = variant["expected"]
                self.assertEqual(lab_outcome(variant["facts"], contract), (expected["status"], expected["reason"]))

    def test_all_three_rules_are_request_rules(self):
        self.assertEqual([r["field"] for r in rp.request_rules()],
                         ["offer_terms_current", "hardship_exit_available", "choice_freely_confirmed"])


class OrganisationGuardTests(unittest.TestCase):
    def test_fixture_is_the_casebook_organisation(self):
        self.assertEqual(rp.ORGANISATION, "Northgate Bank")
        rp.assert_fictional(rp.load_data(), rp.load_contract())

    def test_unmarked_organisation_is_refused(self):
        data = rp.load_data()
        data["organisation"] = "Northgate Bank"
        with self.assertRaises(rp.FictionalOrganisationError):
            rp.assert_fictional(data, rp.load_contract())

    def test_any_other_organisation_is_refused_even_when_marked(self):
        data = rp.load_data()
        data["organisation"] = "Harbor Street Bank (fictional)"
        with self.assertRaises(rp.FictionalOrganisationError):
            rp.assert_fictional(data, rp.load_contract())

    def test_contract_must_be_the_authored_fixture(self):
        contract = rp.load_contract()
        contract["provenance"]["kind"] = "production-policy"
        with self.assertRaises(rp.FictionalOrganisationError):
            rp.assert_fictional(rp.load_data(), contract)

    def test_note_must_say_fictional(self):
        data = rp.load_data()
        data["note"] = "Sample data."
        with self.assertRaises(rp.FictionalOrganisationError):
            rp.assert_fictional(data, rp.load_contract())

    def test_hardship_team_may_not_name_another_organisation(self):
        data = rp.load_data()
        data["hardship_routes"]["card"]["team"] = "Harbor Credit Union hardship desk"
        with self.assertRaises(rp.FictionalOrganisationError):
            rp.assert_fictional(data, rp.load_contract())


class SpokenSpanishTests(unittest.TestCase):
    def test_amounts(self):
        self.assertEqual(rp.spoken_amount("204.00"), "doscientos cuatro dólares")
        self.assertEqual(rp.spoken_amount("102.00"), "ciento dos dólares")
        self.assertEqual(rp.spoken_amount("612.00"), "seiscientos doce dólares")
        self.assertEqual(rp.spoken_amount("151.67"), "ciento cincuenta y un dólares con sesenta y siete centavos")
        self.assertEqual(rp.spoken_amount("2480.00"), "dos mil cuatrocientos ochenta dólares")
        self.assertEqual(rp.spoken_amount("21.00"), "veintiún dólares")
        self.assertEqual(rp.spoken_amount("100.00"), "cien dólares")

    def test_dates_and_references(self):
        self.assertEqual(rp.spoken_date("2026-10-15"), "15 de octubre")
        self.assertEqual(rp.spoken_reference("PLN-402913"), "P, L, N, cuatro, cero, dos, nueve, uno, tres")
        self.assertRegex(rp.make_reference("PLN", "a", "b"), r"^PLN-\d{6}$")

    def test_account_endings_as_spoken_or_typed(self):
        for said in ("4471", "la tarjeta 4471", "cuatro cuatro siete uno", "terminada en 4 4 7 1"):
            with self.subTest(said=said):
                self.assertEqual(rp.normalise_account(said), "4471")


class HardshipAndWithdrawalTests(unittest.TestCase):
    def test_basic_needs_are_hardship(self):
        for said in ("Perdí mi trabajo y no me alcanza para la renta.",
                     "No tengo ni para la comida este mes.",
                     "Apenas me alcanza para los gastos básicos.",
                     "Estoy desempleada desde agosto.",
                     "no puedo cubrir lo básico"):
            with self.subTest(said=said):
                self.assertTrue(rp.hardship_declared([said]))

    def test_wanting_a_plan_is_not_hardship(self):
        for said in ("No puedo pagar todo de una vez.", "Quiero un plan de pagos para mi tarjeta.",
                     "Prefiero hablar con el equipo de apoyo.", "Solo puedo dar 50 dólares al mes."):
            with self.subTest(said=said):
                self.assertIsNone(rp.hardship_declared([said]))

    def test_withdrawals(self):
        for said in ("No, espere, mejor no.", "Ya no quiero ese plan.", "Cancélelo, por favor.", "No."):
            with self.subTest(said=said):
                self.assertTrue(rp.is_withdrawal(said))
        for said in ("Sí.", "Sí, está bien.", "Sí, ese mismo, gracias."):
            with self.subTest(said=said):
                self.assertFalse(rp.is_withdrawal(said))


class OfferTests(unittest.TestCase):
    def setUp(self):
        rp.reset_states()
        self.state = rp.state_for("t")

    def test_current_offers_only_with_the_hardship_exit(self):
        r = rp.get_plan_offers(MARISOL, "4471", convo("Quiero un plan."), self.state)
        self.assertEqual(r["status"], "offers")
        self.assertEqual([o["offer_id"] for o in r["offers"]], ["OFR-4471-3M", "OFR-4471-6M"])
        self.assertEqual(r["offers"][0]["terms_spoken"], "tres pagos mensuales de doscientos cuatro dólares")
        self.assertEqual(r["question"], rp.CASE_QUESTION)
        self.assertIn("team", r["hardship_option"])

    def test_someone_elses_account_looks_like_an_unknown_one(self):
        theirs = rp.get_plan_offers(MARISOL, "6603", convo(), self.state)
        unknown = rp.get_plan_offers(MARISOL, "1234", convo(), self.state)
        strip = lambda r: {k: v for k, v in r.items() if k != "account_ending"}  # noqa: E731
        self.assertEqual(theirs["status"], "not_found")
        self.assertEqual(strip(theirs), strip(unknown))

    def test_loan_offers_are_off_when_its_hardship_team_is_down(self):
        r = rp.get_plan_offers(MARISOL, "0938", convo("Quiero un plan para el préstamo."), self.state)
        self.assertEqual((r["status"], r["reason"]), ("blocked", "hardship_path_missing"))
        self.assertEqual(r["offers"], [])

    def test_no_offers_after_hardship_is_declared(self):
        r = rp.get_plan_offers(MARISOL, "4471", convo("Perdí mi trabajo, no me alcanza para la comida."),
                               self.state)
        self.assertEqual(r["status"], "hardship_declared")
        self.assertEqual(r["offers"], [])


class SelectAndRecordTests(unittest.TestCase):
    def setUp(self):
        rp.reset_states()
        self.state = rp.state_for("t")

    def stage(self, offer_id=None, account="4471", users=("Quiero el plan de tres pagos.",), **kw):
        return rp.select_plan_offer(MARISOL, account, convo(*users), self.state, offer_id, **kw)

    def record(self, offer_id, memory, answer="Sí.", question=None, users=("Quiero el plan de tres pagos.",)):
        c = convo(*users, question=question if question is not None else question_for(offer_id), answer=answer)
        return rp.record_plan_choice(MARISOL, c, self.state, offer_id, memory, "t")

    def test_a_confirmed_current_offer_is_recorded_from_the_fixture(self):
        staged, memory = self.stage("OFR-4471-3M")
        self.assertEqual(staged["status"], "staged")
        self.assertFalse(staged["recorded"])
        r = self.record("OFR-4471-3M", memory)
        self.assertEqual((r["status"], r["effects"]), ("succeeded", 1))
        self.assertEqual((r["installments"], r["amount_usd"], r["first_due"]), (3, "204.00", "2026-10-15"))
        self.assertEqual(r["payment_status"], "no_payment_received")
        self.assertFalse(r["debit_scheduled"])
        self.assertRegex(r["reference"], r"^PLN-\d{6}$")
        self.assertIsNone(self.state.staged)

    def test_a_plan_described_by_the_customer_is_matched_to_the_offer(self):
        staged, memory = self.stage(installments=6, amount_usd=102)
        self.assertEqual(staged["offer_id"], "OFR-4471-6M")

    def test_the_letter_offer_is_stale(self):
        staged, memory = self.stage(installments=4, amount_usd="153")
        self.assertEqual((staged["status"], staged["reason"], staged["detail"]),
                         ("blocked", "stale_plan_terms", "expired"))
        self.assertIsNone(memory)
        staged, _ = self.stage("OFR-4471-LTR")
        self.assertEqual(staged["reason"], "stale_plan_terms")

    def test_a_made_up_plan_is_not_offered(self):
        staged, memory = self.stage(installments=12, amount_usd=50)
        self.assertEqual((staged["reason"], staged["detail"]), ("stale_plan_terms", "not_offered"))
        self.assertEqual([o["offer_id"] for o in staged["current_offers"]], ["OFR-4471-3M", "OFR-4471-6M"])
        staged, _ = self.stage(amount_usd=50)
        self.assertEqual(staged["detail"], "not_offered")

    def test_the_loan_plan_cannot_be_staged_while_its_hardship_team_is_down(self):
        staged, memory = self.stage("OFR-0938-2M", account="0938")
        self.assertEqual(staged["reason"], "hardship_path_missing")
        self.assertIsNone(memory)

    def test_record_needs_the_read_back_of_this_offer(self):
        _, memory = self.stage("OFR-4471-3M")
        r = self.record("OFR-4471-3M", memory, question=question_for("OFR-4471-6M"))
        self.assertEqual((r["reason"], r["detail"]), ("choice_not_confirmed", "not_read_back"))
        r = self.record("OFR-4471-3M", memory, question="")
        self.assertEqual(r["detail"], "not_read_back")

    def test_record_needs_an_answer(self):
        _, memory = self.stage("OFR-4471-3M")
        r = self.record("OFR-4471-3M", memory, answer=None)
        self.assertEqual(r["detail"], "not_answered")

    def test_a_withdrawn_answer_records_nothing(self):
        _, memory = self.stage("OFR-4471-3M")
        r = self.record("OFR-4471-3M", memory, answer="No, espere, mejor no.")
        self.assertEqual((r["status"], r["reason"], r["detail"], r["effects"]),
                         ("blocked", "choice_not_confirmed", "withdrawn", 0))
        self.assertIsNone(self.state.staged)
        self.assertEqual(self.state.plans, [])

    def test_record_refuses_an_offer_that_was_not_staged(self):
        _, memory = self.stage("OFR-4471-3M")
        r = self.record("OFR-4471-6M", memory)
        self.assertEqual(r["detail"], "not_staged")
        r = rp.record_plan_choice(MARISOL, convo(), rp.state_for("fresh"), "OFR-4471-3M", {}, "fresh")
        self.assertEqual((r["reason"], r["detail"]), ("choice_not_confirmed", "not_staged"))

    def test_no_plan_after_hardship_even_if_the_customer_then_asks(self):
        users = ("No me alcanza para la renta.", "Bueno, anóteme en el de seis pagos.")
        staged, memory = self.stage("OFR-4471-6M", users=users)
        self.assertEqual((staged["status"], staged["detail"]), ("hardship_declared", "hardship_declared"))
        self.assertIsNone(memory)
        self.state.staged = {"account_ending": "4471", "offer_id": "OFR-4471-6M", "tag": "OFR-4471-6M/1"}
        r = self.record("OFR-4471-6M", {"plan_tag": "OFR-4471-6M/1"}, users=users)
        self.assertEqual((r["reason"], r["detail"], r["effects"]), ("choice_not_confirmed", "hardship_declared", 0))

    def test_no_plan_after_a_hardship_referral(self):
        rp.request_hardship_referral(MARISOL, "4471", "prefiere apoyo", self.state, "t")
        staged, memory = self.stage("OFR-4471-3M")
        self.assertEqual(staged["status"], "hardship_declared")

    def test_a_second_stage_needs_its_own_read_back(self):
        _, first = self.stage("OFR-4471-3M")
        _, second = self.stage("OFR-4471-6M")
        self.assertNotEqual(first["plan_tag"], second["plan_tag"])
        r = self.record("OFR-4471-6M", first)
        self.assertEqual(r["detail"], "not_staged")
        self.assertEqual(self.record("OFR-4471-6M", second)["status"], "succeeded")

    def test_memory_values_stay_under_the_prompt_limit(self):
        for account in ("4471", "0938"):
            for offer in rp.load_data()["accounts"][account]["offers"]:
                values = rp.plan_memory_values(rp.load_data()["accounts"][account], offer, offer["offer_id"] + "/9")
                self.assertTrue(all(len(v) < rp.MEMORY_VALUE_LIMIT for v in values.values()))
        self.assertLess(len(rp.session_profile()["account_list"]), rp.MEMORY_VALUE_LIMIT)


class WithdrawReferralCallbackTests(unittest.TestCase):
    def setUp(self):
        rp.reset_states()
        self.state = rp.state_for("t")

    def test_withdraw_a_recorded_plan(self):
        _, memory = rp.select_plan_offer(MARISOL, "4471", convo(), self.state, "OFR-4471-6M")
        rp.record_plan_choice(MARISOL, convo(question=question_for("OFR-4471-6M"), answer="Sí."), self.state,
                              "OFR-4471-6M", memory, "t")
        r = rp.withdraw_plan_choice(self.state, "4471")
        self.assertEqual((r["status"], r["plan_status"], r["debit_scheduled"]), ("withdrawn", "withdrawn", False))
        self.assertIsNone(self.state.active_plan())

    def test_withdraw_before_recording_clears_the_stage(self):
        rp.select_plan_offer(MARISOL, "4471", convo(), self.state, "OFR-4471-3M")
        r = rp.withdraw_plan_choice(self.state)
        self.assertEqual((r["status"], r["staged_choice_cleared"], r["effects"]), ("nothing_recorded", True, 0))

    def test_card_hardship_referral(self):
        r = rp.request_hardship_referral(MARISOL, "4471", "perdió su trabajo", self.state, "t")
        self.assertEqual((r["status"], r["offers_paused"]), ("referred", True))
        self.assertRegex(r["reference"], r"^HRD-\d{6}$")

    def test_loan_hardship_request_is_preserved_with_a_callback(self):
        r = rp.request_hardship_referral(MARISOL, "0938", "no le alcanza", self.state, "t")
        self.assertEqual((r["status"], r["referral_preserved"]), ("callback_requested", True))
        self.assertRegex(r["callback_reference"], r"^CB-\d{6}$")

    def test_human_callback_records_no_plan(self):
        r = rp.request_human_callback(MARISOL, "0938", "plan de pagos", self.state, "t")
        self.assertEqual((r["status"], r["plan_recorded"]), ("callback_requested", False))
        self.assertEqual(rp.request_human_callback(MARISOL, "6603", "x", self.state, "t")["status"], "not_found")

    def test_receipts_are_spanish_and_say_no_payment(self):
        _, memory = rp.select_plan_offer(MARISOL, "4471", convo(), self.state, "OFR-4471-3M")
        r = rp.record_plan_choice(MARISOL, convo(question=question_for("OFR-4471-3M"), answer="Sí."), self.state,
                                  "OFR-4471-3M", memory, "t")
        text = rp.customer_receipt("record_plan_choice", r)
        self.assertIn("tres pagos mensuales de doscientos cuatro dólares", text)
        self.assertIn("no hemos recibido ningún pago", text)
        self.assertIsNone(rp.customer_receipt("record_plan_choice", {"status": "blocked"}))


class ConversationTests(unittest.TestCase):
    def test_reads_the_latest_question_and_its_answer(self):
        events = [
            UserUttered(text="/session_start", metadata={}),
            UserUttered(text="Quiero el de tres pagos.", metadata={}),
            BotUttered(text="Pregunta vieja", metadata={"utter_action": rp.CONFIRM_UTTER}),
            UserUttered(text="Mejor el de seis.", metadata={}),
            BotUttered(text="Pregunta nueva", metadata={"utter_action": rp.CONFIRM_UTTER}),
            UserUttered(text="Sí.", metadata={}),
            UserUttered(text="Gracias.", metadata={}),
        ]
        c = conversation_from_events(events)
        self.assertEqual(c.user_texts, ("Quiero el de tres pagos.", "Mejor el de seis.", "Sí.", "Gracias."))
        self.assertEqual((c.confirmation_question, c.confirmation_answer), ("Pregunta nueva", "Sí."))

    def test_a_question_not_yet_answered(self):
        c = conversation_from_events([BotUttered(text="Q", metadata={"utter_action": rp.CONFIRM_UTTER})])
        self.assertIsNone(c.confirmation_answer)


class ToolTimeoutTests(unittest.TestCase):
    def test_timeout_leaves_room_for_a_spoken_receipt(self):
        """ToolContext.send on voice waits for the receipt to be spoken (about 3 s per 100 characters)."""
        text = (PROJECT / "agent.yml").read_text()
        timeout = float(text.split("\ntool_timeout:")[1].split()[0])
        longest = max(len(rp.customer_receipt("record_plan_choice", {
            "status": "succeeded", "reference_spoken": rp.spoken_reference("PLN-000000"),
            "account_label": a["label"], "terms_spoken": rp._offer_view(o)["terms_spoken"],
            "first_due_spoken": rp.spoken_date(o["first_due"])}))
            for a in rp.load_data()["accounts"].values() for o in a["offers"])
        self.assertGreaterEqual(timeout, 2 * 3 * longest / 100)


class ResponsesTests(unittest.TestCase):
    def test_the_read_back_carries_the_terms_the_guard_checks(self):
        text = (PROJECT / "skills" / "repayment_plan" / "responses.yml").read_text()
        for slot in ("{plan_account_label}", "{plan_terms_label}", "{plan_first_due_label}"):
            self.assertIn(slot, text)
        self.assertNotIn("utter_on_user_denial", (PROJECT / "skills" / "repayment_plan" / "skill.md").read_text())


if __name__ == "__main__":
    unittest.main()
