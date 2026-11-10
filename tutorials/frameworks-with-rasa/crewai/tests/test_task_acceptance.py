"""Native structured task records exercise the application acceptance boundary."""

import copy
import unittest
from crewai.crews.crew_output import CrewOutput
from crewai.tasks.task_output import TaskOutput
from crewai.tools.tool_failure import ToolFailure, ToolFailureRecord
from claim_crew.acceptance import PUBLIC_SOURCES, inspect_result


def output():
    source = PUBLIC_SOURCES["vehicle"]
    tasks = [
        TaskOutput(
            name="source",
            description="Read source",
            agent="Researcher",
            json_dict=source.model_dump(),
        ),
        TaskOutput(
            name="checklist",
            description="Prepare checklist",
            agent="Writer",
            json_dict={"claim_type": "vehicle", "documents": source.required_documents},
        ),
    ]
    return CrewOutput(raw="A finished-looking answer", tasks_output=tasks)


class TaskAcceptance(unittest.TestCase):
    def test_complete_records_are_accepted(self):
        self.assertEqual(inspect_result(output(), "vehicle")["status"], "ready")

    def test_missing_source_is_incomplete(self):
        result = output()
        result.tasks_output.pop(0)
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_duplicate_task_name_is_incomplete(self):
        result = output()
        result.tasks_output[0].name = "checklist"
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_old_revision_is_incomplete(self):
        result = output()
        result.tasks_output[0].json_dict["revision"] = "2026-10-01"
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_extra_action_field_is_incomplete(self):
        result = output()
        result.tasks_output[1].json_dict["claim_filed"] = True
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_missing_document_is_incomplete(self):
        result = output()
        result.tasks_output[1].json_dict["documents"].pop()
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_bad_task_data_is_incomplete(self):
        result = output()
        result.tasks_output[0].json_dict = None
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_earlier_tool_failure_survives_final_task(self):
        result = output()
        result.tasks_output[0].tool_failures.append(
            ToolFailureRecord(
                tool_name="read_claim_source",
                failure=ToolFailure(message="Unavailable", code="source_unavailable"),
            )
        )
        self.assertEqual(inspect_result(result, "vehicle")["status"], "incomplete")

    def test_selected_claim_type_is_application_owned(self):
        self.assertEqual(inspect_result(output(), "travel")["status"], "incomplete")

    def test_returned_records_do_not_mutate_task_outputs(self):
        result = output()
        before = copy.deepcopy(result.tasks_output[0].json_dict)
        accepted = inspect_result(result, "vehicle")
        accepted["source"]["required_documents"].clear()
        self.assertEqual(result.tasks_output[0].json_dict, before)
