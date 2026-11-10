"""Use committed Pipecat turns for a Rasa dialogue; keep audio in Pipecat."""

import asyncio
from collections.abc import Awaitable, Callable

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InterruptionFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.utils.errors import ErrorCategory, classify_http_exception


class RasaDialogueProcessor(FrameProcessor):
    def __init__(self, ask: Callable[[str], Awaitable[list[str]]], **kwargs):
        super().__init__(**kwargs)
        self.ask = ask
        self._generation = 0
        self._requests = set()
        self._dialogue_lock = asyncio.Lock()
        self._closing = False
        self.discarded_responses = 0
        self.skipped_speculations = 0
        self.rejected_contexts = 0
        self.request_failures = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Invalidate before parent interruption processing can yield.
        if isinstance(frame, (InterruptionFrame, CancelFrame, EndFrame)):
            self._generation += 1
        if isinstance(frame, (CancelFrame, EndFrame)):
            self._closing = True
        await super().process_frame(frame, direction)
        if (
            isinstance(frame, LLMContextFrame)
            and direction == FrameDirection.DOWNSTREAM
        ):
            if frame.speculation:
                self.skipped_speculations += 1
                return
            self._generation += 1
            messages = frame.context.get_messages()
            last = messages[-1] if messages else {}
            text = last.get("content") if last.get("role") == "user" else None
            if (
                self._closing
                or not isinstance(text, str)
                or not text.strip()
                or len(text) > 1000
            ):
                self.rejected_contexts += 1
                return
            generation = self._generation
            task = self.create_task(self._answer(generation, text))
            self._requests.add(task)
            task.add_done_callback(self._requests.discard)
            return
        await self.push_frame(frame, direction)

    async def _answer(self, generation: int, text: str):
        try:
            # Keep accepted dialogue requests in order. Interruption changes
            # speech ownership; it cannot undo a request accepted by Rasa.
            async with self._dialogue_lock:
                if self._closing or generation != self._generation:
                    self.discarded_responses += 1
                    return
                replies = await self.ask(text)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.request_failures += 1
            if self._owns_response(generation):
                # Expose a native operational error without raw request/provider
                # details and without presenting invented text as an answer.
                await self.push_error(
                    "Rasa dialogue request unavailable",
                    category=classify_http_exception(error)
                    or ErrorCategory.APPLICATION,
                )
            return
        if not self._owns_response(generation):
            self.discarded_responses += 1
            return
        if not replies:
            return
        await self.push_frame(LLMFullResponseStartFrame())
        if not self._owns_response(generation):
            self.discarded_responses += 1
            return
        # REST records are complete messages, not whitespace-preserving token
        # deltas. Keep their boundaries in the single native text frame.
        await self.push_frame(LLMTextFrame("\n".join(replies)))
        if self._owns_response(generation):
            await self.push_frame(LLMFullResponseEndFrame())

    def _owns_response(self, generation: int) -> bool:
        return generation == self._generation and not self._closing

    async def wait_for_requests(self):
        """Wait for currently owned requests; useful before orderly shutdown."""
        while self._requests:
            await asyncio.gather(*tuple(self._requests))

    async def cleanup(self):
        self._closing = True
        self._generation += 1
        for task in tuple(self._requests):
            await self.cancel_task(task)
        await super().cleanup()
