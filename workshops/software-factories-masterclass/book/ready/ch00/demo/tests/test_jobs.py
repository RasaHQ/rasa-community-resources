"""Author-owned service controls; constructed data, no provider or model IO."""
import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.jobs import Answer, BriefingRefused, Jobs, Owner
from briefing.identity import IdentityRefused, SENDER_META
from zeo_core.integrations.agents import TurnResult


class JobControls(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.owner = Owner("authenticated-mantle-peer", "conversation-a")
        self.other = Owner("authenticated-mantle-peer", "conversation-b")

        async def incomplete(work):
            return Answer(TurnResult("managed-a", "incomplete", ""), {})

        self.jobs = Jobs(incomplete)

    async def asyncTearDown(self):
        await self.jobs.close()

    async def test_start_is_prompt_and_foreign_get_revise_are_refused(self):
        response = await self.jobs.briefing(self.owner, action="start", request="Brief my flight")
        self.assertEqual(response["status"], "started")
        for action, extra in (("get", {}), ("revise", {"change": "new destination"})):
            with self.assertRaisesRegex(BriefingRefused, "job_unavailable"):
                await self.jobs.briefing(self.other, action=action, job_id=response["job_id"], **extra)

    async def test_display_snapshot_has_no_capability_and_foreign_get_cannot_select_board(self):
        from briefing.replay import ReplayRunner
        runner = ReplayRunner()
        self.jobs = Jobs(runner, replacement_plan=runner.replacement_plan)
        response = await self.jobs.briefing(self.owner, action="start", request="Replay DEMO101")
        capability = response["job_id"]
        await self.jobs._jobs[capability].task
        board = self.jobs.display_snapshot()
        self.assertEqual(self.jobs.display_title(), "Flight briefing")
        self.assertEqual(len(board), 3)
        self.assertNotIn(capability, repr(board))
        other = await self.jobs.briefing(self.other, action="start", request="Replay DEMO101 missing meeting")
        await self.jobs._jobs[other["job_id"]].task
        with self.assertRaises(BriefingRefused):
            await self.jobs.briefing(self.other, action="get", job_id=capability)
        self.assertFalse(self.jobs.display_snapshot())
        self.assertIn("meeting date and time required", self.jobs.display_title())
        self.assertNotIn(capability, self.jobs.display_title())
        await self.jobs.briefing(self.owner, action="get", job_id=capability)
        self.assertEqual(self.jobs.display_snapshot(), board)
        await self.jobs.close()
        self.assertFalse(self.jobs.display_snapshot())

    async def test_identity_is_not_a_public_argument_and_mixed_args_refuse(self):
        with self.assertRaisesRegex(BriefingRefused, "conversation_identity_required"):
            await self.jobs.briefing(None, action="start", request="Brief my flight")
        for kwargs in ({"action": "start", "request": "x", "change": "y"},
                       {"action": "get", "request": "x"},
                       {"action": "revise", "job_id": "x"}):
            with self.assertRaises(BriefingRefused):
                await self.jobs.briefing(self.owner, **kwargs)

    async def test_authenticated_metadata_boundary_preserves_two_conversation_isolation(self):
        a = {SENDER_META: "conversation-a"}
        b = {SENDER_META: "conversation-b"}
        response = await self.jobs.from_transport("mantle-peer", a, action="start", request="Brief my flight")
        for action, extra in (("get", {}), ("revise", {"change": "Change the flight"})):
            with self.assertRaisesRegex(BriefingRefused, "job_unavailable"):
                await self.jobs.from_transport("mantle-peer", b, action=action, job_id=response["job_id"], **extra)
        with self.assertRaises(IdentityRefused):
            await self.jobs.from_transport(None, a, action="get", job_id=response["job_id"])

    async def test_completed_text_without_cards_and_tool_records_is_not_complete(self):
        async def text_only(work):
            return Answer(TurnResult("managed-a", "completed", "A model claim"), {})
        self.jobs = Jobs(text_only)
        response = await self.jobs.briefing(self.owner, action="start", request="Brief my flight")
        await self.jobs._jobs[response["job_id"]].task
        state = await self.jobs.briefing(self.owner, action="get", job_id=response["job_id"])
        self.assertEqual(state["status"], "incomplete")
        self.assertEqual(state["widgets"], [])

    async def test_late_uncancellable_result_cannot_overwrite_revised_job(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def runner(work):
            if work.revision == 1:
                started.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                return Answer(TurnResult("old-session", "completed", "Old destination"), {})
            return Answer(TurnResult("new-session", "incomplete", ""), {})

        self.jobs = Jobs(runner)
        response = await self.jobs.briefing(self.owner, action="start", request="Old destination")
        job_id = response["job_id"]
        old = self.jobs._jobs[job_id].task
        await started.wait()
        revised = await self.jobs.briefing(self.owner, action="revise", job_id=job_id, change="New destination")
        await self.jobs._jobs[job_id].task
        release.set()
        await old
        self.assertEqual(revised["revision"], 2)
        self.assertEqual(self.jobs._jobs[job_id].session_id, "new-session")
        state = await self.jobs.briefing(self.owner, action="get", job_id=job_id)
        self.assertEqual(state["status"], "incomplete")
        self.assertEqual(state["cards"], [])

    async def test_timeout_is_explicit_and_has_no_current_cards(self):
        async def waiting(work):
            await asyncio.Event().wait()
        self.jobs = Jobs(waiting, timeout=0.01)
        response = await self.jobs.briefing(self.owner, action="start", request="Brief my flight")
        await self.jobs._jobs[response["job_id"]].task
        state = await self.jobs.briefing(self.owner, action="get", job_id=response["job_id"])
        self.assertEqual((state["status"], state["reason"]), ("incomplete", "briefing_timeout"))
        self.assertEqual(state["cards"], [])


if __name__ == "__main__":
    unittest.main()
