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

    async def test_missing_inputs_are_asked_and_same_job_resumes_with_explicit_values(self):
        started = await self.jobs.briefing(self.owner, action="start", request="Replay DEMO101 missing inputs")
        job_id = started["job_id"]
        async def inspect():
            await self.jobs._jobs[job_id].task
            return await self.jobs.briefing(self.owner, action="get", job_id=job_id)
        state = await inspect()
        self.assertEqual(state["status"], "needs_input")
        self.assertEqual(state["needs_input"]["field"], "meeting_time")
        self.assertEqual(state["cards"], [])
        self.assertIsNone(self.jobs._jobs[job_id].turn)
        for invalid in ("tomorrow at five", "2026-10-22T21:00:00"):
            await self.jobs.briefing(self.owner, action="revise", job_id=job_id, change=invalid)
            state = await inspect()
            self.assertEqual(state["status"], "needs_input")
            self.assertEqual(state["needs_input"]["field"], "meeting_time")
        await self.jobs.briefing(self.owner, action="revise", job_id=job_id, change="2026-10-22T21:00:00Z")
        state = await inspect()
        self.assertEqual(state["status"], "needs_input")
        self.assertEqual(state["needs_input"]["field"], "transfer_minutes")
        for invalid in ("guess", "-5", "90 hours", "1500 minutes"):
            await self.jobs.briefing(self.owner, action="revise", job_id=job_id, change=invalid)
            state = await inspect()
            self.assertEqual(state["status"], "needs_input")
            self.assertEqual(state["needs_input"]["field"], "transfer_minutes")
        resumed = await self.jobs.briefing(self.owner, action="revise", job_id=job_id, change="45 minutes")
        self.assertEqual(resumed["job_id"], job_id)
        state = await inspect()
        self.assertEqual(state["status"], "complete", state)
        self.assertNotIn("needs_input", state)
        text = render_cards(state)
        self.assertIn("Transfer assumption: 45 minutes", text)
        self.assertIn("Margin: 165.0 minutes", text)
        await self.jobs.briefing(self.owner, action="revise", job_id=job_id, change="Replay DEMO101 later arrival")
        later = await inspect()
        self.assertIn("Margin: 75.0 minutes", render_cards(later))
        self.assertIn("Transfer assumption: 45 minutes", render_cards(later))

    async def test_flight_failure_keeps_weather_and_replaces_old_values_with_errors(self):
        job_id, original = await self.start()
        old_ids = {card["data_ref"]["id"] for card in original["cards"]}
        await self.jobs.briefing(self.owner, action="revise", job_id=job_id,
                                change="Replay DEMO101 flight unavailable")
        await self.jobs._jobs[job_id].task
        state = await self.jobs.briefing(self.owner, action="get", job_id=job_id)
        self.assertEqual(state["status"], "incomplete")
        cards = {card["event"]["component"]: card for card in state["cards"]}
        for component in ("flight_status", "arrival_timeline"):
            self.assertEqual(cards[component]["data_ref"]["payload"], {})
            self.assertIsNotNone(cards[component]["data_ref"]["error"])
        self.assertEqual(len(cards["weather_hourly"]["data_ref"]["payload"]["hourly"]), 3)
        self.assertIsNone(cards["weather_hourly"]["data_ref"]["payload"]["arrival_hour"])
        self.assertFalse(old_ids & {card["data_ref"]["id"] for card in state["cards"]})
        text = render_cards(state)
        self.assertIn("Unavailable: Flight source", text)
        self.assertNotIn("Margin:", text)
        self.assertNotIn("Estimated arrival:", text)
        self.assertIn("Weather Hourly", text)
        await self.jobs.briefing(self.owner, action="revise", job_id=job_id, change="Replay DEMO101")
        await self.jobs._jobs[job_id].task
        recovered = await self.jobs.briefing(self.owner, action="get", job_id=job_id)
        self.assertEqual(recovered["status"], "complete")
        self.assertIn("Margin: 120.0 minutes", render_cards(recovered))

    async def test_missing_estimate_uses_labelled_schedule_without_inventing_delay(self):
        started = await self.jobs.briefing(self.owner, action="start", request="Replay DEMO101 no estimate")
        job_id = started["job_id"]
        await self.jobs._jobs[job_id].task
        state = await self.jobs.briefing(self.owner, action="get", job_id=job_id)
        self.assertEqual(state["status"], "complete", state)
        cards = {card["event"]["component"]: card for card in state["cards"]}
        flight = cards["flight_status"]["data_ref"]["payload"]
        self.assertIsNone(flight["estimated_arrival"])
        self.assertEqual(flight["reported_status"], "Classroom replay status")
        rendered = render_cards(state)
        self.assertIn("Arrival from scheduled_arrival", rendered)
        self.assertIn("Estimated arrival: not provided", rendered)
        self.assertIn("Margin: 150.0 minutes", rendered)


if __name__ == "__main__":
    unittest.main()
