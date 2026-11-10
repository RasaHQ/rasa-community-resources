"""Actual Pipecat worker/queues with controlled dialogue replies and a text sink."""

import asyncio
import inspect
import textwrap

from pipecat.frames.frames import (
    EndFrame,
    InterruptionFrame,
    LLMContextFrame,
    LLMTextFrame,
    StartFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.workers.runner import WorkerRunner
from rasa_dialogue.processor import RasaDialogueProcessor


class Capture(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.frames = []
        self.started = asyncio.Event()
        self.interrupted = asyncio.Event()

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        self.frames.append(frame)
        if isinstance(frame, StartFrame):
            self.started.set()
        if isinstance(frame, InterruptionFrame):
            self.interrupted.set()
        await self.push_frame(frame, direction)

    @property
    def text(self):
        return [frame.text for frame in self.frames if isinstance(frame, LLMTextFrame)]


class ControlledDialogue:
    def __init__(self):
        self.calls = []
        self.started = asyncio.Queue()
        self.active = 0
        self.max_active = 0

    async def __call__(self, text):
        future = asyncio.get_running_loop().create_future()
        self.calls.append(text)
        self.active += 1
        self.max_active = max(self.active, self.max_active)
        await self.started.put(future)
        try:
            return await future
        finally:
            self.active -= 1

    async def next_request(self):
        return await asyncio.wait_for(self.started.get(), 3)


class NativePipeline:
    def __init__(self, processor):
        self.processor = processor
        self.capture = Capture()
        self.worker = PipelineWorker(
            Pipeline([processor, self.capture]),
            enable_rtvi=False,
            enable_turn_tracking=False,
            idle_timeout_secs=None,
        )
        self.errors = []

        @self.worker.event_handler("on_pipeline_error")
        async def on_error(worker, frame):
            self.errors.append(frame)

        self.runner = WorkerRunner(handle_sigint=False)

    async def __aenter__(self):
        await self.runner.add_workers(self.worker)
        self.running = asyncio.create_task(self.runner.run())
        await asyncio.wait_for(self.capture.started.wait(), 3)
        return self

    async def feed(self, frame):
        await self.worker.queue_frames([frame])
        assert await self.worker.flush_pipeline(timeout=3)

    async def settle_requests(self, *, timeout=3):
        await asyncio.wait_for(self.processor.wait_for_requests(), timeout)
        assert await self.worker.flush_pipeline(timeout=3)

    async def __aexit__(self, *error):
        if error[0] is not None:
            await self.worker.cancel(reason="fixture failed")
        else:
            await self.worker.queue_frames([EndFrame()])
        await asyncio.wait_for(self.running, 5)


def context_frame(text="Public area question", *, speculation=False):
    return LLMContextFrame(
        LLMContext([{"role": "user", "content": text}]), speculation=speculation
    )


def ownership_mutation():
    """Remove only the response generation comparison from the actual method."""
    source = textwrap.dedent(inspect.getsource(RasaDialogueProcessor._owns_response))
    guard = "generation == self._generation and "
    assert source.count(guard) == 1
    namespace = {}
    exec(
        compile(source.replace(guard, ""), "<response-owner-mutation>", "exec"),
        namespace,
    )
    return type(
        "UncheckedResponseOwner",
        (RasaDialogueProcessor,),
        {"_owns_response": namespace["_owns_response"]},
    )


async def observe_late_response(*, remove_ownership_guard=False):
    dialogue = ControlledDialogue()
    cls = ownership_mutation() if remove_ownership_guard else RasaDialogueProcessor
    processor = cls(dialogue)
    async with NativePipeline(processor) as pipeline:
        await pipeline.feed(context_frame())
        pending = await dialogue.next_request()
        await pipeline.feed(InterruptionFrame())
        await asyncio.wait_for(pipeline.capture.interrupted.wait(), 3)
        pending.set_result(["Synthetic old answer."])
        await pipeline.settle_requests()
        observation = {
            "generation_guard": "removed" if remove_ownership_guard else "present",
            "native_interruption_reached_sink": pipeline.capture.interrupted.is_set(),
            "dialogue_requests": len(dialogue.calls),
            "response_text_after_interruption": pipeline.capture.text,
            "discarded_responses": processor.discarded_responses,
        }
    return observation
