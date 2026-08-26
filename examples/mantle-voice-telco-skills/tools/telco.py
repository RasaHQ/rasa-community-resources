"""Shared telecom tools used by session start and multiple skills."""

from __future__ import annotations

import random
from typing import Optional

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import (
    SPEED_THRESHOLD_MBPS,
    Database,
    customer_id_from_context,
    get_customer_by_id,
    get_customer_by_name,
    username_from_context,
)


@tool(description="Load the demo customer profile into project memory.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    """Ensure username / customer_id / plan details are available."""
    username = username_from_context(context)
    customer_id = customer_id_from_context(context)
    db = Database()

    row = get_customer_by_name(db, username)
    if not row:
        row = get_customer_by_id(db, customer_id)
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "customer_not_found",
                "username": username,
                "customer_id": customer_id,
            }
        )

    cid, first_name, last_name, name, email, address, plan_name = row
    if context is not None:
        context.memory.set("username", name)
        context.memory.set("customer_id", str(cid))
        context.memory.set("plan_name", plan_name)
        context.memory.set("email_address", email)
        context.memory.set("physical_address", address)

    return ToolResult(
        llm_response={
            "ok": True,
            "username": name,
            "first_name": first_name,
            "last_name": last_name,
            "customer_id": str(cid),
            "plan_name": plan_name,
            "email_address": email,
            "physical_address": address,
        }
    )


@tool(description="Run a network speed test and return download speed in Mbps.")
async def run_speed_test(context: ToolContext = None) -> ToolResult:
    """Simulate a download speed test for the active customer line."""
    override = None
    if context is not None:
        override = context.memory.get("network_speed_override")

    if override is not None:
        try:
            speed = float(override)
        except (TypeError, ValueError):
            speed = float(random.randint(10, 140))
    else:
        speed = float(random.randint(10, 140))

    speed = round(speed, 1)
    is_slow = speed < SPEED_THRESHOLD_MBPS

    if context is not None:
        context.memory.set("network_speed", speed)
        context.memory.set("speed_is_slow", is_slow)

    return ToolResult(
        llm_response={
            "ok": True,
            "download_mbps": speed,
            "threshold_mbps": SPEED_THRESHOLD_MBPS,
            "is_slow": is_slow,
            "message": (
                f"Your network download speed is {speed} Mbps."
                if is_slow
                else f"{speed} Mbps — that looks healthy."
            ),
        }
    )
