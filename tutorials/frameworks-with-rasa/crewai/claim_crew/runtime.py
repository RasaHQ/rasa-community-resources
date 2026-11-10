"""The existing research crew, independent of its customer-facing conversation."""

from crewai import Agent, Crew, Task, Process
from crewai.llms.base_llm import BaseLLM
from crewai.tools import BaseTool
from crewai.tools.tool_failure import ToolFailure, ToolFailurePolicy
from .acceptance import SourceRecord, Checklist, PUBLIC_SOURCES


class ReadClaimSource(BaseTool):
    name: str = "read_claim_source"
    description: str = "Read the selected public synthetic claim-document source."
    claim_type: str
    unavailable: bool = False

    def _run(self):
        if self.unavailable:
            return ToolFailure(
                message="Synthetic source temporarily unavailable",
                code="source_unavailable",
                retryable=True,
            )
        return PUBLIC_SOURCES[self.claim_type].model_dump_json()


def create_claim_crew(
    claim_type: str, model: BaseLLM, unavailable: bool = False
) -> Crew:
    source = PUBLIC_SOURCES[claim_type]
    checklist = Checklist(claim_type=claim_type, documents=source.required_documents)
    reader = Agent(
        role="Public source researcher",
        goal="Read the selected source",
        backstory="Use the registered public source tool.",
        llm=model,
        tools=[ReadClaimSource(claim_type=claim_type, unavailable=unavailable)],
        allow_delegation=False,
        max_iter=4,
        verbose=False,
        cache=False,
    )
    writer = Agent(
        role="Document checklist writer",
        goal="Retain required document names",
        backstory="Prepare a public checklist without approving or filing a claim.",
        llm=model,
        allow_delegation=False,
        max_iter=4,
        verbose=False,
        cache=False,
    )
    source_task = Task(
        name="source",
        description="Read the selected public source using read_claim_source.",
        expected_output="A source JSON record",
        output_json=SourceRecord,
        agent=reader,
    )
    checklist_task = Task(
        name="checklist",
        description="Return the required public document names from the source.",
        expected_output="A checklist JSON record",
        output_json=Checklist,
        agent=writer,
        context=[source_task],
    )
    return Crew(
        agents=[reader, writer],
        tasks=[source_task, checklist_task],
        process=Process.sequential,
        planning=False,
        memory=False,
        cache=False,
        verbose=False,
        tool_failure_policy=ToolFailurePolicy.WARN,
    )
