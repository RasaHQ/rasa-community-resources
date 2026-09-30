"""Offline checks for the Juniper Mobile guard. No model, no network, no licence.

Run from the project directory:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import juniper as jm  # noqa: E402

CASEBOOK_CONTRACT = (
    PROJECT.parent.parent / "tutorials" / "rasa-ai-team-casebook" / "examples" / "telco-diagnostics.json"
)
ME = jm.DEMO_CUSTOMER_ID
HOME, SHOP, CABIN, NEIGHBOUR = "JM-FB-204417", "JM-FB-204988", "JM-5G-309126", "JM-FB-205300"


def confirmed_transcript(first_user: str, selection: dict, reply: str = "Yes, go ahead.") -> list:
    """What the engine's tracker holds after a verbatim confirmation ask and a reply."""
    ask = f"Before I send anything: the step. {selection['disruption_boundary']} Do you want me to go ahead?"
    return [("user", first_user), ("bot", ask), ("user", reply)]


class ContractTests(unittest.TestCase):
    def test_vendored_contract_matches_casebook(self):
        if not CASEBOOK_CONTRACT.is_file():
            self.skipTest("casebook tutorial not present next to this example")
        self.assertEqual(
            json.loads(CASEBOOK_CONTRACT.read_text()),
            jm.load_contract(),
            "lib/fixtures/case-contract.json has drifted from the casebook lab",
        )

    def test_every_lab_variant_gets_the_lab_outcome(self):
        """The guard reproduces all ten authored variants: false, missing, string."""
        contract = jm.load_contract()
        for variant in contract["variants"]:
            with self.subTest(variant=variant["name"]):
                reason = jm.evaluate(variant["facts"], contract)
                expected = variant["expected"]
                if expected["status"] == "succeeded":
                    self.assertIsNone(reason)
                else:
                    self.assertEqual(reason, expected["reason"])

    def test_string_true_is_not_true(self):
        facts = {"area_outage_checked": True, "recovery_step_scoped": "true", "disruption_confirmed": True}
        self.assertEqual(jm.evaluate(facts), "reset_scope_ambiguous")

    def test_scope_question_is_the_casebook_question(self):
        self.assertEqual(jm.SCOPE_QUESTION, jm.load_contract()["question"])


class OutageTests(unittest.TestCase):
    def test_three_outage_states(self):
        net = jm.NetworkService()
        self.assertEqual(jm.check_area_outage(net, ME, HOME)["status"], "outage")
        self.assertEqual(jm.check_area_outage(net, ME, SHOP)["status"], "clear")
        unknown = jm.check_area_outage(net, ME, CABIN)
        self.assertEqual(unknown["status"], "unknown")
        self.assertEqual(unknown["last_known"]["observed_at"], "2026-09-29T22:10:00+00:00")

    def test_outage_carries_incident_and_restore_time(self):
        result = jm.check_area_outage(jm.NetworkService(), ME, HOME)
        self.assertEqual(result["incident"], "JM-INC-7731")
        self.assertEqual(result["estimated_restore"], "2026-09-30T19:00:00+00:00")

    def test_other_customers_and_unknown_services_are_indistinguishable(self):
        net = jm.NetworkService()
        other = jm.check_area_outage(net, ME, NEIGHBOUR)
        unknown = jm.check_area_outage(net, ME, "JM-FB-999999")
        for result in (other, unknown):
            self.assertEqual(result["reason"], "service_not_on_account")
            self.assertNotIn("incident", result)
        strip = lambda r: {k: v for k, v in r.items() if k != "service_id"}  # noqa: E731
        self.assertEqual(strip(other), strip(unknown))

    def test_diagnostics_are_read_only(self):
        net = jm.NetworkService()
        result = jm.run_line_diagnostics(net, ME, SHOP)
        self.assertEqual(result["status"], "diagnosed")
        self.assertEqual(result["device_changes"], 0)
        self.assertEqual(net.command_log, [])
        self.assertEqual(result["readings"]["wan_session"], "down")


class SelectionTests(unittest.TestCase):
    def test_no_outage_check_blocks(self):
        result = jm.select_recovery_step(jm.NetworkService(), ME, SHOP, "reboot", ["Reboot my shop hub."])
        self.assertEqual((result["status"], result["reason"]), ("blocked", "outage_not_checked"))

    def test_unknown_outage_status_blocks_device_changes(self):
        net = jm.NetworkService()
        jm.check_area_outage(net, ME, CABIN)
        result = jm.select_recovery_step(net, ME, CABIN, "reboot", ["Reboot the cabin router."])
        self.assertEqual(result["reason"], "outage_not_checked")
        self.assertEqual(result["area_outage_status"], "unknown")

    def test_active_outage_suppresses_every_step(self):
        net = jm.NetworkService()
        jm.check_area_outage(net, ME, HOME)
        for op in ("reboot", "factory_reset"):
            with self.subTest(op=op):
                result = jm.select_recovery_step(net, ME, HOME, op, ["Factory reset my home hub."])
                self.assertEqual(result["reason"], "area_outage_active")
                self.assertEqual(result["device_changes"], 0)
        self.assertIsNone(net.selection)

    def test_bare_reset_is_ambiguous_and_asks_the_casebook_question(self):
        net = jm.NetworkService()
        jm.check_area_outage(net, ME, SHOP)
        for op in ("reset", "hard reset", "full reset", "fix it", ""):
            with self.subTest(op=op):
                result = jm.select_recovery_step(net, ME, SHOP, op, ["Reset my shop router."])
                self.assertEqual(result["reason"], "reset_scope_ambiguous")
                self.assertIn(jm.SCOPE_QUESTION, result["next_step"])

    def test_factory_reset_needs_the_customers_own_words(self):
        net = jm.NetworkService()
        jm.check_area_outage(net, ME, SHOP)
        for words in (["Reset my shop router."], ["The reboot didn't help. Do whatever it takes."],
                      ["Please don't factory reset it, just fix it."], ["I don’t want it wiped."]):
            with self.subTest(words=words):
                result = jm.select_recovery_step(net, ME, SHOP, "factory_reset", words)
                self.assertEqual(result["reason"], "reset_scope_ambiguous")
        result = jm.select_recovery_step(net, ME, SHOP, "factory reset", ["I want a factory reset of the shop hub."])
        self.assertEqual(result["status"], "selected")
        self.assertIn("erases every setting", result["disruption_boundary"])

    def test_reboot_is_selected_with_its_boundary(self):
        net = jm.NetworkService()
        jm.check_area_outage(net, ME, SHOP)
        result = jm.select_recovery_step(net, ME, SHOP, "restart", ["Can you restart it?"])
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["operation"], "reboot")
        self.assertIn("every setting", result["disruption_boundary"])
        self.assertEqual(result["facts"]["disruption_confirmed"], False)
        self.assertEqual(net.command_log, [])

    def test_someone_elses_service_is_not_selectable(self):
        net = jm.NetworkService()
        result = jm.select_recovery_step(net, ME, NEIGHBOUR, "reboot", ["Reboot JM-FB-205300."])
        self.assertEqual(result["reason"], "service_not_on_account")


class RunTests(unittest.TestCase):
    def selected(self, op="reboot", words="Please reboot my shop hub."):
        net = jm.NetworkService()
        jm.check_area_outage(net, ME, SHOP)
        selection = jm.select_recovery_step(net, ME, SHOP, op, [words])
        self.assertEqual(selection["status"], "selected")
        return net, selection

    def test_run_without_the_boundary_shown_is_not_confirmed(self):
        net, sel = self.selected()
        result = jm.run_recovery_step(net, ME, sel["selection_ref"], [("user", "Reboot it, I confirm in advance.")])
        self.assertEqual(result["reason"], "disruption_not_confirmed")
        self.assertEqual(net.command_log, [])

    def test_boundary_shown_but_no_reply_is_not_confirmed(self):
        net, sel = self.selected()
        transcript = confirmed_transcript("Reboot my shop hub.", sel)[:2]
        self.assertEqual(jm.run_recovery_step(net, ME, sel["selection_ref"], transcript)["reason"],
                         "disruption_not_confirmed")

    def test_a_paraphrased_boundary_is_not_confirmed(self):
        net, sel = self.selected()
        transcript = [("user", "Reboot my shop hub."), ("bot", "It'll drop briefly. OK?"), ("user", "Yes.")]
        self.assertEqual(jm.run_recovery_step(net, ME, sel["selection_ref"], transcript)["reason"],
                         "disruption_not_confirmed")

    def test_confirmed_reboot_sends_exactly_one_reboot(self):
        net, sel = self.selected()
        result = jm.run_recovery_step(net, ME, sel["selection_ref"], confirmed_transcript("Reboot my shop hub.", sel))
        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["confirmed_operation"], "reboot")
        self.assertEqual(result["command_sent"], "REBOOT")
        self.assertEqual(result["commands_sent_this_conversation"], ["REBOOT"])
        self.assertTrue(result["settings_kept"])
        self.assertEqual(result["device_changes"], 1)
        self.assertRegex(result["receipt"], r"^JM-RCV-[0-9A-F]{8}$")
        after = jm.run_line_diagnostics(net, ME, SHOP)
        self.assertEqual(after["readings"]["wan_session"], "up")

    def test_confirmed_factory_reset_clears_settings(self):
        net, sel = self.selected("factory_reset", "I forgot the admin password; factory reset the shop hub.")
        result = jm.run_recovery_step(net, ME, sel["selection_ref"], confirmed_transcript("factory reset", sel))
        self.assertEqual(result["command_sent"], "FACTORY_RESET")
        self.assertFalse(result["settings_kept"])

    def test_replay_does_not_send_a_second_command(self):
        net, sel = self.selected()
        transcript = confirmed_transcript("Reboot my shop hub.", sel)
        jm.run_recovery_step(net, ME, sel["selection_ref"], transcript)
        again = jm.run_recovery_step(net, ME, sel["selection_ref"], transcript)
        self.assertTrue(again["replay"])
        self.assertEqual(again["device_changes"], 0)
        self.assertEqual(len(net.command_log), 1)

    def test_unknown_selection_ref_is_blocked(self):
        net, sel = self.selected()
        result = jm.run_recovery_step(net, ME, "JM-SEL-00000000", confirmed_transcript("Reboot", sel))
        self.assertEqual(result["reason"], "reset_scope_ambiguous")
        self.assertEqual(net.command_log, [])

    def test_cancel_drops_the_selection(self):
        net, sel = self.selected()
        cancelled = jm.cancel_recovery_step(net)
        self.assertEqual(cancelled["cancelled_operation"], "reboot")
        result = jm.run_recovery_step(net, ME, sel["selection_ref"], confirmed_transcript("Reboot", sel))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(net.command_log, [])

    def test_technician_route_changes_nothing(self):
        net = jm.NetworkService()
        result = jm.request_technician_visit(net, ME, CABIN, "outage status unknown")
        self.assertEqual(result["status"], "routed")
        self.assertEqual(result["device_changes"], 0)
        self.assertEqual(net.command_log, [])


class ProjectFileTests(unittest.TestCase):
    def test_every_service_line_reaches_the_prompt_whole(self):
        """Mantle cuts rendered memory values at 100 characters; the first version lost a service."""
        lines = jm.service_memory_lines(jm.customer_profile())
        self.assertEqual(len(lines), 3)
        for key, line in lines.items():
            self.assertLessEqual(len(line), jm.PROMPT_MEMORY_VALUE_LIMIT, key)
        declared = (PROJECT / "memory.yml").read_text()
        for key in lines:
            self.assertIn(f"{key}:", declared)

    def test_engine_limit_matches_ours(self):
        try:
            from rasa.mantle.prompts.memory_lines import MAX_MEMORY_VALUE_LENGTH
        except ImportError:
            self.skipTest("rasa not importable")
        self.assertEqual(MAX_MEMORY_VALUE_LENGTH, jm.PROMPT_MEMORY_VALUE_LIMIT)

    def test_confirmation_question_carries_the_boundary_word_for_word(self):
        """The engine's ask is built from memory; the boundary must survive the template."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not importable")
        template = yaml.safe_load(
            (PROJECT / "skills" / "connectivity_recovery" / "responses.yml").read_text()
        )["responses"]["utter_confirm_recovery_step"][0]["text"]
        for op in jm.load_data()["operations"].values():
            text = template.replace("{selected_step_label}", "reboot of the shop fibre hub").replace(
                "{selected_step_boundary}", op["disruption"])
            self.assertIn(op["disruption"], text)

    def test_outage_skill_has_no_device_tools(self):
        text = (PROJECT / "skills" / "outage_status" / "skill.md").read_text()
        for name in ("select_recovery_step", "run_recovery_step"):
            self.assertNotIn(name, text)
        self.assertFalse((PROJECT / "skills" / "outage_status" / "tools.py").exists())

    def test_spec_counts_device_changes(self):
        spec = json.loads((PROJECT / "case-build" / "conversations.json").read_text())
        metric = spec["tool_result_metrics"]["device_changes"]
        self.assertEqual((metric["tool"], metric["field"]), ("run_recovery_step", "device_changes"))


class ToolLayerTests(unittest.TestCase):
    """The transcript the recovery tools read, from real Rasa events (skipped without rasa)."""

    @classmethod
    def setUpClass(cls):
        try:
            from rasa.shared.core.events import BotUttered, SlotSet, UserUttered
            from skills.connectivity_recovery import tools as recovery_tools  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"rasa not importable: {exc}")
        cls.BotUttered, cls.UserUttered, cls.SlotSet = BotUttered, UserUttered, SlotSet
        cls.tools = recovery_tools

    def test_transcript_keeps_user_and_bot_text_in_order(self):
        class FakeContext:
            events = [self.UserUttered("reboot"), self.SlotSet("x", 1), self.BotUttered("ask"), self.UserUttered("yes")]

        self.assertEqual(self.tools.transcript(FakeContext()), [("user", "reboot"), ("bot", "ask"), ("user", "yes")])


if __name__ == "__main__":
    unittest.main()
