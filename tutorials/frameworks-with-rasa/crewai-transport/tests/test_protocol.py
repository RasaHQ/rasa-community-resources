import json
import subprocess
import unittest
from unittest.mock import patch
from crew_transport import CrewProcess, SOURCES, checked_response


class Protocol(unittest.TestCase):
    def ready(self, kind="vehicle"):
        return {
            "status": "ready",
            "source": dict(SOURCES[kind]),
            "checklist": {
                "claim_type": kind,
                "documents": list(SOURCES[kind]["required_documents"]),
            },
        }

    def test_only_selected_public_source_and_exact_checklist_are_accepted(self):
        record = self.ready()
        self.assertEqual(checked_response(record, "vehicle"), record)
        self.assertEqual(checked_response(record, "travel")["status"], "incomplete")
        record["checklist"]["documents"].append("Unsupported document")
        self.assertEqual(checked_response(record, "vehicle")["status"], "incomplete")

    def test_extra_action_and_stale_revision_are_withheld(self):
        for change in ("action", "revision"):
            record = self.ready()
            if change == "action":
                record["file_claim"] = True
            else:
                record["source"]["revision"] = "2020-01-01"
            self.assertEqual(
                checked_response(record, "vehicle")["status"], "incomplete"
            )

    def test_invalid_input_never_starts_worker(self):
        with patch("crew_transport.subprocess.run") as run:
            for kind, question in (
                ([], "help"),
                ("unknown", "help"),
                ("vehicle", ""),
                ("vehicle", {}),
                ("vehicle", "x" * 1001),
            ):
                self.assertEqual(
                    CrewProcess().checklist(kind, question)["status"], "incomplete"
                )
            run.assert_not_called()

    def test_input_is_json_and_command_is_fixed(self):
        question = "$(touch /tmp/should-never-execute)"
        with patch(
            "crew_transport.subprocess.run",
            return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(self.ready()), ""
            ),
        ) as run:
            self.assertEqual(
                CrewProcess(python="/trusted/python").checklist("vehicle", question)[
                    "status"
                ],
                "ready",
            )
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], "/trusted/python")
        self.assertTrue(args[0][1].endswith("/crewai/worker.py"))
        self.assertNotIn(question, args[0])
        self.assertEqual(json.loads(kwargs["input"])["question"], question)
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["timeout"], 25)
        self.assertNotIn("RASA_PRO_LICENSE", kwargs["env"])

    def test_worker_failures_and_malformed_or_large_output_are_withheld(self):
        for result in (
            subprocess.CompletedProcess([], 1, "private backend error", ""),
            subprocess.CompletedProcess([], 0, "not json", ""),
            subprocess.CompletedProcess([], 0, "x" * 65537, ""),
        ):
            with patch("crew_transport.subprocess.run", return_value=result):
                self.assertEqual(
                    CrewProcess().checklist("vehicle", "help"),
                    {"status": "incomplete", "reason": "research_unavailable"},
                )
        with patch(
            "crew_transport.subprocess.run",
            side_effect=subprocess.TimeoutExpired("worker", 25),
        ):
            self.assertEqual(
                CrewProcess().checklist("vehicle", "help")["status"], "incomplete"
            )

    def test_actual_native_worker_produces_checked_vehicle_and_travel(self):
        for kind in SOURCES:
            result = CrewProcess(fixture=True).checklist(kind, "Which documents?")
            self.assertEqual(result, self.ready(kind))

    def test_actual_failed_native_tool_cannot_become_a_checklist(self):
        result = CrewProcess(fixture=True, unavailable=True).checklist(
            "vehicle", "Which documents?"
        )
        self.assertEqual(
            result, {"status": "incomplete", "reason": "research_not_complete"}
        )


if __name__ == "__main__":
    unittest.main()
