"""A fixed policy source for the FAQ skill.

This is the ground truth that `generative_response_is_grounded` assertions are
checked against. The same strings appear under `ground_truth:` in
`eval/scenarios/faq_grounded_answer.yml` and `faq_unknown_topic_refused.yml` —
when you change a policy here, change it there too, or the judge will
correctly report the agent as ungrounded against a stale source.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

_POLICIES = {
    "card_replacement": (
        "A replacement debit card is issued free of charge once per calendar "
        "year. Additional replacements cost $12 each. Standard delivery takes "
        "five to seven business days."
    ),
    "overdraft_fee": (
        "The overdraft fee is $28 per transaction, charged at most three times "
        "per day. Accounts overdrawn by $5 or less are not charged a fee."
    ),
    "branch_hours": (
        "Branches are open Monday to Friday from 9am to 5pm, and Saturday from "
        "9am to 1pm. All branches are closed on Sunday and on public holidays."
    ),
}


@tool(
    description=(
        "Look up the bank's stated policy for a topic. Valid topics are "
        "'card_replacement', 'overdraft_fee' and 'branch_hours'."
    )
)
async def lookup_policy(topic: str, context: ToolContext = None) -> ToolResult:
    """Return the policy text for a topic, or an explicit miss."""
    policy = _POLICIES.get(str(topic or "").strip().lower())

    if policy is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "unknown_topic",
                "topic": topic,
                "known_topics": sorted(_POLICIES),
            }
        )

    return ToolResult(llm_response={"ok": True, "topic": topic, "policy": policy})
