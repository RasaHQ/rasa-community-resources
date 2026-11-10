"""Compare failure representation and policy through actual native tool calls."""

from typing import ClassVar
from crewai.tools.tool_failure import ToolFailurePolicy
from .runtime import ReadClaimSource
from .native_fixture import create_fixture
from .acceptance import inspect_result


class ObservedSource(ReadClaimSource):
    declared: bool = True
    observations: ClassVar[list[dict]] = []

    def _run(self):
        failure = super()._run()
        text = failure.as_agent_message()
        self.observations.append({"declared": self.declared, "error_text": text})
        return failure if self.declared else text


def failure_case(declared: bool, policy: ToolFailurePolicy):
    crew = create_fixture("vehicle", unavailable=True)
    source = ObservedSource(claim_type="vehicle", unavailable=True, declared=declared)
    # Task construction captures its tools. Replace both native registrations,
    # then observe _run so the string arm cannot use the original handler.
    crew.agents[0].tools = [source]
    crew.tasks[0].tools = [source]
    crew.tool_failure_policy = policy
    ObservedSource.observations.clear()
    try:
        result = crew.kickoff()
        row = {
            "declared": declared,
            "policy": policy.value,
            "completed_tasks": len(result.tasks_output),
            "final_output_present": bool(result.raw),
            "recorded_tool_failures": len(result.tool_failures),
            "handoff_status": inspect_result(result, "vehicle")["status"],
        }
    except Exception as error:
        row = {
            "declared": declared,
            "policy": policy.value,
            "exception": type(error).__name__,
        }
    row["tool_calls"] = len(ObservedSource.observations)
    row["observed_results"] = list(ObservedSource.observations)
    return row


def failure_matrix():
    return [
        failure_case(declared, policy)
        for declared in (False, True)
        for policy in ToolFailurePolicy
    ]
