"""Leave tools for the HR assistant."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

LEAVE_DATA: dict = {
    "balances": {
        "E001": {
            "annual": {
                "available_days": 12,
                "policy_note": "Balance is shown for demonstration; confirm the official HR record before planning leave.",
            },
            "sick": {
                "available_days": 6,
                "policy_note": "Balance is shown for demonstration; applicable policy and documentation rules still apply.",
            },
        },
        "E002": {
            "annual": {
                "available_days": 10,
                "policy_note": "Balance is shown for demonstration; confirm the official HR record before planning leave.",
            },
            "sick": {
                "available_days": 3,
                "policy_note": "Balance is shown for demonstration; applicable policy and documentation rules still apply.",
            },
        },
        "E003": {
            "annual": {
                "available_days": 9,
                "policy_note": "Balance is shown for demonstration; confirm the official HR record before planning leave.",
            },
            "sick": {
                "available_days": 4,
                "policy_note": "Balance is shown for demonstration; applicable policy and documentation rules still apply.",
            },
        },
        "E004": {
            "annual": {
                "available_days": 8,
                "policy_note": "Balance is shown for demonstration; confirm the official HR record before planning leave.",
            },
            "sick": {
                "available_days": 1,
                "policy_note": "Balance is shown for demonstration; applicable policy and documentation rules still apply.",
            },
        },
    },
    "new_request": {
        "request_number": "LV-NEW-DEMO",
        "status": "Pending approval",
        "next_step": "The authorized approver must review the request.",
    },
}


def _load_leave_data() -> dict:
    return LEAVE_DATA


@tool(description="Check the configured leave balance for an employee and leave type.")
async def check_leave_balance(
    employee_id: str,
    leave_type: str,
    context: ToolContext = None,
) -> ToolResult:
    """Return a leave balance or a not-found response."""
    data = _load_leave_data()
    employee_balance = data["balances"].get(employee_id.upper())
    leave_balance = employee_balance.get(leave_type.lower()) if employee_balance else None
    if employee_balance is None or leave_balance is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "found": False,
                "employee_id": employee_id,
                "leave_type": leave_type,
            }
        )
    else:
        return ToolResult(
            llm_response={
                "ok": True,
                "found": True,
                "demo": True,
                "employee_id": employee_id.upper(),
                "leave_type": leave_type.lower(),
                **leave_balance,
            }
        )


@tool(description="Submit a leave request after the employee reviewed and confirmed the dates and details.")
async def submit_leave_request(
    employee_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    request_note: str,
    context: ToolContext = None,
) -> ToolResult:
    """Return the configured demo response for a new leave request."""
    request = _load_leave_data()["new_request"]
    return ToolResult(
        llm_response={
            "ok": True,
            "demo": True,
            "request_number": request["request_number"],
            "status": request["status"],
            "next_step": request["next_step"],
        }
    )
