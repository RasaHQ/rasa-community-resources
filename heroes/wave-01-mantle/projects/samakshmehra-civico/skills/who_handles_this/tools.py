"""Tool for the who_handles_this skill.

Not everyone who calls a complaint line wants to file a complaint. Some people
just want to know who to talk to — and answering that in twenty seconds,
without walking them through an intake they did not ask for, is a real service.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import directory, speech, store


@tool(description="Say which department and ward officer handles a problem in an area.")
async def who_handles(category: str = "", area: str = "",
                      context: ToolContext = None) -> ToolResult:
    """Answer who owns a kind of problem, optionally in a specific area.

    Args:
        category: One of pothole, garbage, water_supply, streetlight,
            drainage, stray_animals. Leave empty to answer for the area alone.
        area: The locality or PIN code. Leave empty to answer for the
            department alone.

    Files nothing and changes nothing.
    """
    answer: dict = {"ok": True, "helpline": directory._directory()["helpline"]}

    key = store.normalise_category(category)
    routes = store.routing()
    if key and key in routes:
        answer["category"] = key
        answer["problem"] = routes[key]["spoken"]
        answer["department"] = routes[key]["department"]
        answer["target_days"] = routes[key]["sla_days"]
    elif category:
        answer["unsupported_category"] = category
        answer["supported"] = list(routes.keys())

    if area:
        matches = directory.find_ward(area)["matches"]
        if matches:
            best = matches[0]
            answer["locality"] = best["label"]
            answer["ward"] = store.say_ward(best["ward_id"])
            answer["zone"] = best["zone"]
            answer["officer"] = best["officer_name"]
            answer["officer_contact"] = best["officer_contact"]
        else:
            answer["area_not_found"] = area

    if context is not None:
        await context.send(_spoken_answer(answer))
        context.memory.set("answered", True)
    answer["already_read_out_to_the_caller"] = True

    return ToolResult(llm_response=answer)


def _spoken_answer(answer: dict) -> str:
    """Assemble the reply here rather than leaving it to the model.

    Asked as free prose, the model said "I am not sure I can place
    Indirapuram" about a locality sitting in the directory — it had never
    called the lookup at all. The facts are all present by this point, so the
    sentence is assembled where the facts are.
    """
    parts: list[str] = []

    if "department" in answer:
        if "officer" in answer:
            parts.append(
                f"{answer['department']} handles {answer['problem']} in "
                f"{answer['locality']}, and the ward officer is "
                f"{answer['officer']} on {answer['officer_contact']}."
            )
        else:
            parts.append(f"{answer['department']} handles {answer['problem']}.")
        parts.append(f"The usual target is {speech.say_days(answer['target_days'])}.")
    elif "officer" in answer:
        parts.append(
            f"{answer['locality']} is ward {answer['ward']}, in the "
            f"{answer['zone']} zone. The ward officer is {answer['officer']} "
            f"on {answer['officer_contact']}."
        )

    if "area_not_found" in answer:
        parts.append(
            f"I could not place {answer['area_not_found']} in the ward "
            f"directory, so please call the main helpline on "
            f"{answer['helpline']} for that."
        )
    if "unsupported_category" in answer:
        parts.append(
            "This line only handles potholes, garbage, water supply, street "
            "lights, drainage and stray animals."
        )
    if not parts:
        parts.append(
            f"Tell me the problem or the area and I can say who handles it. "
            f"The main helpline is {answer['helpline']}."
        )
    return " ".join(parts)
