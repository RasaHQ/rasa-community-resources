"""Constructed replay through real Core, service state and text presentation.

No network listener, Mantle model, provider, live agent or voice is exercised.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "project")]
from briefing.jobs import Jobs, Owner
from briefing.replay import ReplayRunner
from lib.card_text import render_cards


class ReplayWorkflow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        runner = ReplayRunner()
        self.jobs = Jobs(runner, replacement_plan=runner.replacement_plan)
        self.owner = Owner("verified-test-peer", "conversation-a")

    async def asyncTearDown(self):
        await self.jobs.close()

    async def start(self):
        response = await self.jobs.briefing(self.owner, action="start", request="Replay DEMO101")
        job_id = response["job_id"]
        await self.jobs._jobs[job_id].task
        result = await self.jobs.briefing(self.owner, action="get", job_id=job_id)
        self.assertEqual(result["status"], "complete", result)
        return job_id, result

    async def test_three_cards_are_source_backed_and_replay_is_visible(self):
        job_id, result = await self.start()
        self.assertEqual(len(result["cards"]), 3)
        self.assertEqual(len(self.jobs._jobs[job_id].turn.calls), 3)
        self.assertTrue(all(card["data_ref"]["replay"] for card in result["cards"]))
        text = render_cards(result)
        self.assertEqual(text.count("[REPLAY]"), 3)
        self.assertIn("Margin: 120.0 minutes", text)
        self.assertIn("Arrival from estimated_arrival", text)
        self.assertIn("provider update time not given", text)

    async def test_weather_only_followup_retains_flight_and_timeline_provenance(self):
        job_id, original = await self.start()
        before = {card["event"]["component"]: card for card in original["cards"]}
        await self.jobs.briefing(self.owner, action="revise", job_id=job_id,
                                 change="Replay DEMO101 morning weather")
        pending = await self.jobs.briefing(self.owner, action="get", job_id=job_id)
        replaced = [card for card in pending["cards"] if card["replaced"]]
        self.assertEqual(len(replaced), 1)
        self.assertNotIn("data_ref", replaced[0])
        self.assertIn("superseded; replacement pending", render_cards(pending))
        await self.jobs._jobs[job_id].task
        updated = await self.jobs.briefing(self.owner, action="get", job_id=job_id)
        self.assertEqual(updated["status"], "complete", updated)
        after = {card["event"]["component"]: card for card in updated["cards"]}
        for component in ("flight_status", "arrival_timeline"):
            self.assertEqual(before[component], after[component])
        self.assertNotEqual(before["weather_hourly"]["event"]["request_id"],
                            after["weather_hourly"]["event"]["request_id"])
        self.assertIsNone(after["weather_hourly"]["data_ref"]["payload"]["arrival_hour"])
        self.assertEqual(len(self.jobs._jobs[job_id].turn.calls), 1)


if __name__ == "__main__":
    unittest.main()
