"""Mantle adapter: the model supplies neither authority nor retry identity."""
import os
from pathlib import Path
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from casebook import execute, load_case, lookup, record_intake


def identity(case_id):
    # The lab operator assigns a stable run ID. A real backend uses the
    # authenticated subject + action revision, resolved from trusted context.
    run_id = os.environ.get('CASEBOOK_RUN_ID', 'rehearsal-1')
    return f'{run_id}-{case_id}'


def database():
    return Path(os.environ.get('CASEBOOK_DATABASE', 'casebook.sqlite'))


@tool(description='Rehearse one supported synthetic case. Returns a lab outcome, never a real customer action.')
async def rehearse_case(case_id: str, context: ToolContext = None) -> ToolResult:
    try:
        spec = load_case(case_id)
        outcome = execute(spec, spec['facts'], identity(case_id), database())
    except ValueError:
        outcome = {'status': 'blocked', 'reason': 'unsupported_lab_input'}
    return ToolResult(llm_response=outcome)


@tool(description='Look up an existing synthetic request; this does not submit or retry an external action.')
async def inspect_case(case_id: str, context: ToolContext = None) -> ToolResult:
    try:
        load_case(case_id)
        outcome = lookup(database(), identity(case_id))
    except ValueError:
        outcome = {'status': 'blocked', 'reason': 'unsupported_lab_input'}
    return ToolResult(llm_response=outcome)


@tool(description='Record an independent synthetic arrival, absence, cancellation request or unmatched outage report after the learner explicitly chooses that route. Does not approve a later action.')
async def record_case_intake(case_id: str, context: ToolContext = None) -> ToolResult:
    try:
        spec = load_case(case_id)
        outcome = record_intake(spec, identity(case_id), database())
    except ValueError:
        outcome = {'status': 'blocked', 'reason': 'unsupported_intake_case'}
    return ToolResult(llm_response=outcome)
