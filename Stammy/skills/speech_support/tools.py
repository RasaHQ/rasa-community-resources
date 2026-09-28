"""Supportive practice plan for children with speech impediments."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@tool(
    description=(
        "Create a gentle, child-friendly speech support plan based on age and "
        "main speaking focus."
    )
)
async def suggest_support_plan(context: ToolContext = None) -> ToolResult:
    """Return a short practice plan and script for the child."""
    if context is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "no_context",
                "hint": "Tool requires a runtime context.",
            }
        )

    child_age = str(context.memory.get("child_age") or "not specified")
    focus_area = str(context.memory.get("focus_area") or "general confidence")

    if "stammer" in focus_area.lower() or "speech" in focus_area.lower():
        exercise = "Take 3 slow breaths in through the nose and out through the mouth before each sentence."
        practice_prompt = "Try saying: 'I can speak slowly and I am safe to try again.'"
        suggestions = [
            "Pause gently instead of rushing.",
            "Use short phrases and a relaxed pace.",
            "Celebrate every effort, even if the word feels hard.",
        ]
    else:
        exercise = "Tap one finger for each word, then say the sentence slowly while keeping your shoulders relaxed."
        practice_prompt = "Try saying: 'I am practicing my words, and my voice is important.'"
        suggestions = [
            "Practice one sentence at a time.",
            "Use a calm voice and small pauses.",
            "Make the activity playful and positive.",
        ]

    context.memory.set("support_focus", focus_area)
    return ToolResult(
        llm_response={
            "ok": True,
            "child_age": child_age,
            "focus_area": focus_area,
            "exercise": exercise,
            "practice_prompt": practice_prompt,
            "suggestions": suggestions,
        }
    )
