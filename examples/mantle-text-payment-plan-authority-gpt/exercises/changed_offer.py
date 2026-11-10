"""Replay an offer change through the local service, without a model or SDK.

The conversation objects below are fixtures. They assume an engine has already
allowed the acceptance call; they do not interpret an affirmative answer or
exercise Mantle's confirmation dispatcher.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from lib import plans as billing  # noqa: E402


def fixture_question(memory: dict) -> billing.Conversation:
    """Supply the same displayed offer fields as a confirmation test fixture."""
    question = (
        f"The billing team has offered this schedule for account {memory['plan_account']}: "
        f"{memory['offer_terms']} (offer {memory['offer_tag']}). Do you accept this plan?"
    )
    return billing.Conversation(
        confirmation_question=question,
        confirmation_answered=True,
        user_messages=("Yes, I accept.",),
    )


def replay() -> dict:
    service = billing.BillingService()
    customer = billing.SESSION_CUSTOMER_ID
    offer_id = "AG-OFR-4471-A"
    _, original_memory = billing.select_plan_offer(service, customer, offer_id)
    original_question = fixture_question(original_memory)
    original_offer = service.offer_view(offer_id)

    # Sequential fixture edit: service terms change after the original question.
    # This changes both amount and revision; it does not isolate either alone.
    service.offers[offer_id]["revision"] += 1
    service.offers[offer_id]["instalment_usd"] = "200.00"
    revised_offer = service.offer_view(offer_id)

    def attempt(label: str, memory: dict, conversation: billing.Conversation) -> dict:
        facts, _ = billing.acceptance_facts(service, customer, memory, conversation, offer_id)
        before = len(service.plans)
        result = billing.accept_plan_offer(
            service, customer, memory, conversation, offer_id, "changed-offer-exercise"
        )
        return {
            "stage": label,
            "savedOfferTag": memory["offer_tag"],
            "savedTerms": memory["offer_terms"],
            "question": conversation.confirmation_question,
            "facts": facts,
            "status": result["status"],
            "reason": result.get("reason"),
            "effects": result["effects"],
            "plansBefore": before,
            "plansAfter": len(service.plans),
            "recordedTerms": result.get("recorded_terms"),
        }

    stale = attempt("old values, old question", original_memory, original_question)
    _, refreshed_memory = billing.select_plan_offer(service, customer, offer_id)
    stale_question = attempt("new values, old question", refreshed_memory, original_question)
    fresh = attempt("new values, new fixture question", refreshed_memory, fixture_question(refreshed_memory))
    return {
        "scope": "Offline sequential service replay; fixture questions and answers, no native dispatcher or model",
        "fixtureClock": service.data["as_of"],
        "originalOffer": original_offer,
        "revisedOffer": revised_offer,
        "stages": [stale, stale_question, fresh],
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
