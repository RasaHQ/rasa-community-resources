"""The audited tool API every agent calls. No model, no network, no framework."""

from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

CLINIC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLINIC))

from cedar_clinic import instructions, refills, tools  # noqa: E402
from cedar_clinic.audit import ENV_VAR, AuditLog, read_log  # noqa: E402


class AuditedFlowTests(unittest.TestCase):
    def setUp(self):
        refills.reset_services()
        self.audit = AuditLog()
        self.conv = "test-flow"

    def call(self, fn, *args, **kwargs):
        return fn(self.conv, *args, audit=self.audit, **kwargs)

    def test_a_confirmed_request_leaves_a_complete_trail(self):
        verified = self.call(tools.verify_patient, "Maria Alvarez", "1968-03-14")
        patient = verified["patient_id"]
        selected = self.call(tools.select_medication, patient, "lisinopril")
        ref = selected["record_id"]
        self.call(tools.record_confirmation, ref, True, mechanism="test", question=selected["confirmation_question"],
                  answer="Yes, please send it.")
        sent = self.call(tools.send_refill_request, patient, ref, ref, "")
        self.assertEqual(sent["status"], "succeeded")
        trail = [(e["kind"], e["name"]) for e in self.audit.entries(self.conv)]
        self.assertEqual(trail, [("tool", "verify_patient"), ("tool", "select_medication"),
                                 ("confirmation", "record_confirmation"), ("tool", "send_refill_request")])
        last = self.audit.entries(self.conv)[-1]
        self.assertEqual(last["args"], {"record_id": ref, "patient_note": ""})
        self.assertEqual(last["state"], {"patient_id": patient, "selected_record_id": ref})
        self.assertEqual(last["result"]["effects"], 1)
        seqs = [e["seq"] for e in self.audit.entries()]
        self.assertEqual(seqs, sorted(seqs))

    def test_without_confirmation_nothing_is_sent(self):
        patient = self.call(tools.verify_patient, "Maria Alvarez", "1968-03-14")["patient_id"]
        ref = self.call(tools.select_medication, patient, "lisinopril")["record_id"]
        sent = self.call(tools.send_refill_request, patient, ref, ref, "")
        self.assertEqual((sent["status"], sent["reason"]), ("blocked", "medication_not_confirmed"))

    def test_for_model_hides_the_patient_id(self):
        verified = self.call(tools.verify_patient, "Maria Alvarez", "1968-03-14")
        self.assertIn("patient_id", verified)
        self.assertNotIn("patient_id", tools.for_model(verified))

    def test_conversations_are_isolated(self):
        patient = tools.verify_patient("conv-a", "Maria Alvarez", "1968-03-14", audit=self.audit)["patient_id"]
        got = tools.select_medication("conv-b", patient, "lisinopril", audit=self.audit)
        self.assertEqual(got["reason"], "patient_not_verified")
        self.assertEqual({e["conversation_id"] for e in self.audit.entries()}, {"conv-a", "conv-b"})


class ErrorAuditTests(unittest.TestCase):
    def test_a_raising_call_is_audited_as_an_error(self):
        from unittest import mock

        audit = AuditLog()
        with mock.patch.object(refills, "verify_patient", side_effect=RuntimeError("records offline")):
            with self.assertRaises(RuntimeError):
                tools.verify_patient("err", "Maria Alvarez", "1968-03-14", audit=audit)
        (entry,) = audit.entries("err")
        self.assertEqual(entry["result"]["error"], "RuntimeError: records offline")
        self.assertTrue(entry["is_error"])
        self.assertEqual(entry["result"]["status"], "error")

    def test_normal_calls_are_not_errors(self):
        audit = AuditLog()
        tools.verify_patient("ok", "Maria Alvarez", "1968-03-14", audit=audit)
        self.assertFalse(audit.entries("ok")[0]["is_error"])


class AuditFileTests(unittest.TestCase):
    def test_env_path_is_read_at_first_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "audit.jsonl"
            log = AuditLog()
            old = os.environ.get(ENV_VAR)
            os.environ[ENV_VAR] = str(path)
            try:
                log.record("c1", "tool", "verify_patient", args={"a": 1}, result={"status": "x"})
                log.record("c2", "tool", "verify_patient", args={"a": 2}, result={"status": "y"})
            finally:
                if old is None:
                    os.environ.pop(ENV_VAR, None)
                else:
                    os.environ[ENV_VAR] = old
            rows = read_log(path)
            self.assertEqual([r["conversation_id"] for r in rows], ["c1", "c2"])
            self.assertEqual(read_log(path, "c2")[0]["args"], {"a": 2})
            self.assertTrue(all(json.loads(line) for line in path.read_text().splitlines()))


class ToolSurfaceTests(unittest.TestCase):
    """No model-facing tool can carry a dose, strength or quantity, and none approves."""

    MODEL_TOOLS = {"verify_patient", "select_medication", "send_refill_request", "check_request_status",
                   "route_clinical_question"}

    def test_specs_name_exactly_the_model_tools(self):
        self.assertEqual(set(tools.TOOL_SPECS), self.MODEL_TOOLS)

    def test_no_parameter_takes_a_dose(self):
        for name, spec in tools.TOOL_SPECS.items():
            for param in spec["parameters"]:
                self.assertNotRegex(param, r"dose|strength|quantity|mg|approve", f"{name}({param})")

    def test_spec_parameters_match_the_functions(self):
        for name, spec in tools.TOOL_SPECS.items():
            fn_params = set(inspect.signature(getattr(tools, name)).parameters)
            self.assertTrue(set(spec["parameters"]) <= fn_params, name)
            self.assertTrue(set(spec["required"]) <= set(spec["parameters"]), name)

    def test_json_schema_shape(self):
        schema = tools.json_schema("send_refill_request")
        self.assertEqual(schema["parameters"]["required"], ["record_id"])
        self.assertIn("patient_note", schema["parameters"]["properties"])


class InstructionTests(unittest.TestCase):
    def test_system_prompt_carries_every_rule(self):
        prompt = instructions.system_prompt()
        for rule in instructions.RULES:
            self.assertIn(rule, prompt)
        self.assertIn(instructions.PERSONA, prompt)
        self.assertIn(instructions.VOICE_RULES, prompt)

    def test_instructions_name_only_real_tools(self):
        import re

        named = set(re.findall(r"\b([a-z]+(?:_[a-z]+)+)\b", instructions.PROCEDURE + " ".join(instructions.RULES)))
        tool_like = {n for n in named if n.split("_")[0] in {"verify", "select", "send", "check", "route"}}
        self.assertEqual(tool_like - set(tools.TOOL_SPECS), set())


if __name__ == "__main__":
    unittest.main()
