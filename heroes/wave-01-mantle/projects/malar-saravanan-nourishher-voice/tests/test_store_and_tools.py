#!/usr/bin/env python3
"""Deterministic tests for NourishHer's real persistence and tool layer.

These exercise the actual file-backed store and the @tool functions end to
end — no mocks, no fabricated data, and no LLM/network calls (so they never
hit the Groq rate limit). They cover the data-layer half of the MVP
evaluation scenarios (§11): profile creation/correction, natural meal
logging, meal-history retrieval, saved-preference retrieval, conflicting/
repeated corrections, and plan/grocery persistence.

Run with:  make test   (or: uv run python -m unittest discover -s tests)

Conversation-level scenarios that require the LLM (routing, safety wording,
mid-conversation topic changes) are validated live via the REST harness in
README.md; they are intentionally not automated here because the free Groq
tier's 8000 TPM cap makes them non-deterministic.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from lib import store


class FakeTracker:
    def __init__(self, sender_id: str) -> None:
        self.sender_id = sender_id


class FakeHandle:
    def __init__(self, sender_id: str) -> None:
        self.tracker = FakeTracker(sender_id)


class FakeContext:
    """Minimal stand-in for ToolContext exposing the sender-id path tools use."""

    def __init__(self, sender_id: str) -> None:
        self._handle = FakeHandle(sender_id)
        self.is_cancelled = False


def run(coro):
    return asyncio.run(coro)


class StoreAndToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_dir = store.DATA_DIR
        store.DATA_DIR = Path(self._tmp.name)

    def tearDown(self) -> None:
        store.DATA_DIR = self._orig_dir
        self._tmp.cleanup()

    # --- profile CRUD (scenarios 1, 2, 5, 11) --------------------------- #
    def test_profile_create_update_and_correct(self) -> None:
        from tools.profile import get_user_profile, update_user_profile, delete_user_profile

        ctx = FakeContext("priya")
        run(update_user_profile("name", "Priya", context=ctx))
        run(update_user_profile("diet", "vegetarian", context=ctx))
        run(update_user_profile("likes", "idli, dosa, dal", context=ctx))

        prof = run(get_user_profile(context=ctx)).llm_response["profile"]
        self.assertEqual(prof["name"], "Priya")
        self.assertEqual(prof["diet"], "vegetarian")
        self.assertEqual(prof["likes"], ["idli", "dosa", "dal"])

        # Correction: no longer vegetarian (scenario 2 / 11).
        run(delete_user_profile("diet", context=ctx))
        run(update_user_profile("diet", "flexible", context=ctx))
        self.assertEqual(run(get_user_profile(context=ctx)).llm_response["profile"]["diet"], "flexible")

    def test_list_field_dedupes_and_item_delete(self) -> None:
        from tools.profile import update_user_profile, delete_user_profile, get_user_profile

        ctx = FakeContext("kavya")
        run(update_user_profile("dislikes", "mushrooms", context=ctx))
        run(update_user_profile("dislikes", "Mushrooms", context=ctx))  # dup, case-insensitive
        self.assertEqual(run(get_user_profile(context=ctx)).llm_response["profile"]["dislikes"], ["mushrooms"])

        run(update_user_profile("dislikes", "okra", context=ctx))
        run(delete_user_profile("dislikes", "mushrooms", context=ctx))
        self.assertEqual(run(get_user_profile(context=ctx)).llm_response["profile"]["dislikes"], ["okra"])

    def test_unknown_field_is_rejected(self) -> None:
        from tools.profile import update_user_profile

        res = run(update_user_profile("blood_sugar", "high", context=FakeContext("x")))
        self.assertFalse(res.llm_response["ok"])
        self.assertEqual(res.llm_response["error"], "unknown_field")

    # --- meal logging + history (scenarios 3, 6) ------------------------ #
    def test_log_meal_and_retrieve_history(self) -> None:
        from tools.meals import log_meal, get_meal_history

        ctx = FakeContext("ananya")
        run(log_meal("2 idlis, sambar, coffee", "breakfast", "high", context=ctx))
        run(log_meal("a sandwich, not sure what was in it", "lunch", "low", context=ctx))

        hist = run(get_meal_history(1, context=ctx)).llm_response
        self.assertEqual(hist["count"], 2)
        descriptions = [m["description"] for m in hist["meals"]]
        self.assertIn("2 idlis, sambar, coffee", descriptions)
        # Approximate input is stored verbatim with low confidence — not invented.
        low = [m for m in hist["meals"] if m["confidence"] == "low"][0]
        self.assertIn("not sure", low["description"])

    def test_behavioral_summary_counts_only(self) -> None:
        from tools.meals import log_meal, get_behavioral_summary

        ctx = FakeContext("meera")
        run(log_meal("oats and eggs", "breakfast", "high", context=ctx))
        run(log_meal("paneer rice", "lunch", "high", context=ctx))
        summary = run(get_behavioral_summary(7, context=ctx)).llm_response
        self.assertEqual(summary["total_meals_logged"], 2)
        self.assertEqual(summary["meals_by_type"]["breakfast"], 1)
        self.assertIn("Do not infer medical", summary["note"])

    def test_log_meal_respects_cancellation(self) -> None:
        from tools.meals import log_meal, get_meal_history

        ctx = FakeContext("sara")
        ctx.is_cancelled = True
        res = run(log_meal("chicken and rice", "dinner", "high", context=ctx))
        self.assertFalse(res.llm_response["ok"])
        self.assertEqual(run(get_meal_history(1, context=ctx)).llm_response["count"], 0)

    # --- plans + grocery (should-have) ---------------------------------- #
    def test_plan_save_recall_and_grocery(self) -> None:
        from tools.meals import create_meal_plan, get_saved_plan, create_grocery_list

        ctx = FakeContext("priya")
        run(create_meal_plan("2026-09-10", "breakfast: oats; dinner: dal rice", context=ctx))

        got = run(get_saved_plan("2026-09-10", context=ctx)).llm_response
        self.assertTrue(got["ok"])
        self.assertIn("dal rice", got["plan"]["meals"])

        grocery = run(create_grocery_list("2026-09-10", context=ctx)).llm_response
        self.assertTrue(grocery["ok"])
        self.assertIn("oats", grocery["plan_meals"])

        missing = run(get_saved_plan("1999-01-01", context=ctx)).llm_response
        self.assertFalse(missing["ok"])

    # --- per-user isolation (multiple test profiles A–E) ---------------- #
    def test_users_are_isolated(self) -> None:
        from tools.meals import log_meal, get_meal_history

        run(log_meal("dosa", "breakfast", "high", context=FakeContext("userA")))
        run(log_meal("roti", "dinner", "high", context=FakeContext("userB")))
        self.assertEqual(run(get_meal_history(1, context=FakeContext("userA"))).llm_response["count"], 1)
        self.assertEqual(
            run(get_meal_history(1, context=FakeContext("userB"))).llm_response["meals"][0]["description"],
            "roti",
        )

    # --- referral logging (safety adjacent) ----------------------------- #
    def test_referral_is_recorded(self) -> None:
        from tools.meals import request_professional_referral
        from lib import store as s

        ctx = FakeContext("ananya")
        run(request_professional_referral("medication timing question", "pharmacist", context=ctx))
        entries = s.read_log("ananya")
        self.assertEqual(entries[-1]["kind"], "referral")
        self.assertEqual(entries[-1]["referral_type"], "pharmacist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
