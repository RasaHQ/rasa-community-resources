import unittest

from pipecat.frames.frames import (
    InterruptionFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from rasa_dialogue.native_fixture import (
    ControlledDialogue,
    NativePipeline,
    context_frame,
    observe_late_response,
)
from rasa_dialogue.processor import RasaDialogueProcessor


class NativeTurnOwnership(unittest.IsolatedAsyncioTestCase):
    async def test_completed_response_uses_native_response_boundaries(self):
        dialogue = ControlledDialogue()
        async with NativePipeline(RasaDialogueProcessor(dialogue)) as p:
            await p.feed(context_frame())
            pending = await dialogue.next_request()
            pending.set_result(["Synthetic first answer.", "Synthetic second answer."])
            await p.settle_requests()
            self.assertEqual(
                p.capture.text, ["Synthetic first answer.\nSynthetic second answer."]
            )
            self.assertEqual(
                sum(isinstance(f, LLMFullResponseStartFrame) for f in p.capture.frames),
                1,
            )
            self.assertEqual(
                sum(isinstance(f, LLMFullResponseEndFrame) for f in p.capture.frames), 1
            )

    async def test_native_queue_interruption_cannot_reject_a_later_callback_alone(self):
        guarded = await observe_late_response()
        mutation = await observe_late_response(remove_ownership_guard=True)
        self.assertTrue(guarded["native_interruption_reached_sink"])
        self.assertTrue(mutation["native_interruption_reached_sink"])
        self.assertEqual(guarded["dialogue_requests"], 1)
        self.assertEqual(mutation["dialogue_requests"], 1)
        self.assertEqual(guarded["response_text_after_interruption"], [])
        self.assertEqual(
            mutation["response_text_after_interruption"], ["Synthetic old answer."]
        )
        self.assertEqual(guarded["discarded_responses"], 1)

    async def test_next_committed_turn_waits_for_accepted_dialogue_request(self):
        dialogue = ControlledDialogue()
        async with NativePipeline(RasaDialogueProcessor(dialogue)) as p:
            await p.feed(context_frame("Old public question"))
            old = await dialogue.next_request()
            await p.feed(InterruptionFrame())
            await p.feed(context_frame("New public question"))
            self.assertEqual(dialogue.calls, ["Old public question"])
            old.set_result(["Old answer"])
            new = await dialogue.next_request()
            new.set_result(["New answer"])
            await p.settle_requests()
            self.assertEqual(p.capture.text, ["New answer"])
            self.assertEqual(
                dialogue.calls, ["Old public question", "New public question"]
            )
            self.assertEqual(dialogue.max_active, 1)

    async def test_speculative_context_never_starts_a_dialogue_request(self):
        dialogue = ControlledDialogue()
        processor = RasaDialogueProcessor(dialogue)
        async with NativePipeline(processor) as p:
            await p.feed(context_frame(speculation=True))
            self.assertEqual(dialogue.calls, [])
            self.assertEqual(processor.skipped_speculations, 1)
            self.assertEqual(p.capture.text, [])

    async def test_invalid_or_non_user_context_does_not_replay_earlier_user(self):
        dialogue = ControlledDialogue()
        processor = RasaDialogueProcessor(dialogue)
        async with NativePipeline(processor) as p:
            for messages in [
                [],
                [{"role": "developer", "content": "Ask the user to repeat"}],
                [{"role": "assistant", "content": "Old answer"}],
                [{"role": "user", "content": " "}],
                [{"role": "user", "content": "x" * 1001}],
                [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": "Multimodal input"}],
                    }
                ],
            ]:
                await p.feed(LLMContextFrame(LLMContext(messages)))
            self.assertEqual(dialogue.calls, [])
            self.assertEqual(processor.rejected_contexts, 6)

    async def test_failed_dialogue_request_produces_no_speech_text(self):
        dialogue = ControlledDialogue()
        async with NativePipeline(RasaDialogueProcessor(dialogue)) as p:
            await p.feed(context_frame())
            pending = await dialogue.next_request()
            pending.set_exception(RuntimeError("synthetic_request_failure"))
            await p.settle_requests()
            self.assertEqual(p.capture.text, [])
            self.assertEqual(p.processor.request_failures, 1)
            self.assertEqual(
                [f.error for f in p.errors], ["Rasa dialogue request unavailable"]
            )
            self.assertTrue(all(f.exception is None for f in p.errors))

    async def test_superseded_queued_turn_never_starts_another_dialogue_request(self):
        dialogue = ControlledDialogue()
        async with NativePipeline(RasaDialogueProcessor(dialogue)) as p:
            await p.feed(context_frame("Accepted old question"))
            old = await dialogue.next_request()
            await p.feed(context_frame("Superseded queued question"))
            await p.feed(context_frame("Current question"))
            old.set_result(["Old answer"])
            current = await dialogue.next_request()
            current.set_result(["Current answer"])
            await p.settle_requests()
            self.assertEqual(
                dialogue.calls, ["Accepted old question", "Current question"]
            )
            self.assertEqual(p.capture.text, ["Current answer"])
            self.assertEqual(dialogue.max_active, 1)

    async def test_pipeline_shutdown_releases_its_own_pending_request(self):
        dialogue = ControlledDialogue()
        processor = RasaDialogueProcessor(dialogue)
        async with NativePipeline(processor) as p:
            await p.feed(context_frame())
            pending = await dialogue.next_request()
        self.assertTrue(pending.cancelled())
        self.assertEqual(dialogue.active, 0)
        self.assertEqual(processor._requests, set())

    async def test_question_is_captured_before_mutable_context_changes(self):
        dialogue = ControlledDialogue()
        async with NativePipeline(RasaDialogueProcessor(dialogue)) as p:
            frame = context_frame("Committed public question")
            await p.feed(frame)
            pending = await dialogue.next_request()
            frame.context.add_message(
                {"role": "user", "content": "Later unrelated question"}
            )
            pending.set_result(["Committed answer"])
            await p.settle_requests()
            self.assertEqual(dialogue.calls, ["Committed public question"])
            self.assertEqual(p.capture.text, ["Committed answer"])

    async def test_rejected_committed_context_also_retires_the_old_response(self):
        dialogue = ControlledDialogue()
        async with NativePipeline(RasaDialogueProcessor(dialogue)) as p:
            await p.feed(context_frame("Old accepted question"))
            old = await dialogue.next_request()
            await p.feed(context_frame("x" * 1001))
            old.set_result(["Old answer"])
            await p.settle_requests()
            self.assertEqual(dialogue.calls, ["Old accepted question"])
            self.assertEqual(p.capture.text, [])
            self.assertEqual(p.processor.rejected_contexts, 1)
