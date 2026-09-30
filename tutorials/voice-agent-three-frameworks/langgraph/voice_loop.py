# concern: voice-loop
"""One phone call over Rasa's browser_audio protocol, around a LangGraph agent.

LangGraph and LangChain have no audio components, so everything here is
written for this version (shared/web/PROTOCOL.md is the contract):

- audio transport: base64 PCM frames in, forwarded to Speechmatics realtime;
  agent speech out in chunks of up to a second;
- end of turn: Speechmatics' EndOfUtterance (0.7 s of silence) gives one
  final transcript per caller turn (cedar_speech.SpeechmaticsASR); a
  ``{"text"}`` frame is a turn too. Turns are answered one at a time, in order;
- the agent turn: ``agent.astream`` with the model's tokens, the guard's
  ``interrupt()`` and custom events; after an interrupt the next caller turn is
  sent as ``Command(resume=...)``;
- sentence chunking: model tokens are cut at sentence ends and each sentence
  is synthesised as soon as it is complete, while the model keeps streaming;
- fillers: a fixed phrase when the model starts a tool call and nothing has
  been said yet in the turn;
- playback markers: start, one per second of audio, and end with the three
  latency fields;
- silence check-in: after 30 s with no caller speech and no bot audio playing;
- the conversation's events (user, bot, bot_turn_ended) for the events endpoint.

Barge-in is not implemented: audio that arrives while the agent speaks is
transcribed and answered after the current turn, as Rasa does with
interruptions off.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from cedar_clinic import instructions
from cedar_speech import SpeechmaticsASR
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

log = logging.getLogger("cedar.voice")

SAMPLE_RATE = 24000
#: Seconds without caller speech or bot audio before a check-in (Rasa: silence_timeout: 30).
SILENCE_TIMEOUT_S = 30.0
SILENCE_PROMPT = "Are you still there? I can help when you're ready."
#: Barge-in: not implemented; the protocol's interruptPlayback is never sent.
INTERRUPTIONS_ENABLED = False
ERROR_TEXT = "Sorry, something went wrong on my side. Please say that again."
#: Spoken when the model starts a tool call before saying anything in the turn.
FILLERS = {
    "verify_patient": "One moment while I check your details.",
    "select_medication": "Let me look at your record.",
    "check_request_status": "Let me check on that request.",
    "route_clinical_question": "One moment.",
    "send_refill_request": "One moment.",
    "confirmed": "Right, I'll send that request for review.",
}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class Conversation:
    """The events endpoint's record of one call."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def add(self, event: str, text: Optional[str] = None, ts: Optional[float] = None) -> None:
        row: dict = {"event": event, "timestamp": round(ts or time.time(), 6)}
        if text is not None:
            row["text"] = text
        self.events.append(row)


CONVERSATIONS: dict[str, Conversation] = {}


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """Complete sentences in *buffer*, and the unfinished rest."""
    parts = _SENTENCE_END.split(buffer)
    return [p.strip() for p in parts[:-1] if p.strip()], parts[-1]


@dataclass
class TurnClock:
    """When the turn's final transcript arrived, and when its first bot message was ready to speak."""

    started: float
    first_ready: Optional[float] = None

    def ready(self) -> None:
        self.first_ready = self.first_ready or time.time()

    @property
    def processing_ms(self) -> Optional[float]:
        return round((self.first_ready - self.started) * 1000, 1) if self.first_ready else None


@dataclass
class Message:
    """One bot message: spoken as one or more sentences, logged as one bot event."""

    clock: TurnClock
    parts: list[str] = field(default_factory=list)
    buffer: str = ""


class Call:
    def __init__(self, websocket: Any, conversation_id: str, agent: Any, tts: Any, *, use_asr: bool = True) -> None:
        self.ws = websocket
        self.id = conversation_id
        self.agent = agent
        self.tts = tts
        self.use_asr = use_asr
        self.conv = CONVERSATIONS.setdefault(conversation_id, Conversation())
        self.config = {"configurable": {"thread_id": conversation_id}}
        self.out: asyncio.Queue = asyncio.Queue()
        self.turns: asyncio.Queue = asyncio.Queue()
        self.asr: Optional[SpeechmaticsASR] = None
        self.tasks: list[asyncio.Task] = []
        self.unacked: set[str] = set()
        self.busy = False
        self.turn_count = 0
        now = time.time()
        self.last_caller_activity = now
        self.last_playback_done = now

    # -- lifecycle ---------------------------------------------------------------

    async def run(self) -> None:
        await self.ws.send_text(json.dumps({"type": "handshake", "sample_rate": SAMPLE_RATE}))
        if self.use_asr:
            try:
                self.asr = await SpeechmaticsASR(SAMPLE_RATE).open()
            except Exception as exc:  # the call still works with {"text"} frames
                log.error("%s: speech-to-text unavailable: %s", self.id, exc)
        self.tasks = [asyncio.create_task(self._sender()), asyncio.create_task(self._turn_worker()),
                      asyncio.create_task(self._silence_watch())]
        if self.asr is not None:
            self.tasks.append(asyncio.create_task(self._asr_reader()))
        greeting = TurnClock(time.time())
        self._speak_whole(instructions.GREETING, greeting)
        self.out.put_nowait(("turn_end", None))
        try:
            await self._receiver()
        finally:
            await self._hangup()

    async def _hangup(self) -> None:
        # Let a turn in progress finish, so its model calls and audit entries stay with this call.
        worker = self.tasks[1] if len(self.tasks) > 1 else None
        if worker is not None and self.busy:
            try:
                await asyncio.wait_for(asyncio.shield(self._idle()), timeout=60)
            except asyncio.TimeoutError:
                log.warning("%s: turn still running at hangup", self.id)
        for task in self.tasks:
            task.cancel()
        if self.asr is not None:
            await self.asr.close()
            log.info("%s: hangup; %.1f s of audio streamed to speech-to-text", self.id, self.asr.audio_seconds)

    async def _idle(self) -> None:
        while self.busy:
            await asyncio.sleep(0.1)

    # -- inbound -----------------------------------------------------------------

    async def _receiver(self) -> None:
        while True:
            try:
                raw = await self.ws.receive_text()
            except Exception:
                return
            try:
                frame = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(frame, dict):
                continue
            if "audio" in frame:
                if self.asr is not None:
                    try:
                        await self.asr.send_audio(base64.b64decode(frame["audio"]))
                    except Exception as exc:
                        log.error("%s: speech-to-text send failed: %s", self.id, exc)
                        self.asr = None
            elif "text" in frame:
                text = str(frame["text"] or "").strip()
                if text:
                    self.last_caller_activity = time.time()
                    self.turns.put_nowait((text, time.time()))
            elif "marker" in frame:
                self.unacked.discard(str(frame["marker"]))
                if not self.unacked:
                    self.last_playback_done = time.time()

    async def _asr_reader(self) -> None:
        try:
            async for event in self.asr.events():
                self.last_caller_activity = time.time()
                if event.final:
                    self.turns.put_nowait((event.text, event.at))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.error("%s: speech-to-text stopped: %s", self.id, exc)

    # -- turns -------------------------------------------------------------------

    async def _turn_worker(self) -> None:
        while True:
            text, at = await self.turns.get()
            self.busy = True
            self.turn_count += 1
            self.conv.add("user", text, ts=at)
            clock = TurnClock(at)
            try:
                await self._agent_turn(text, clock)
            except Exception as exc:
                log.exception("%s: agent turn failed: %s", self.id, exc)
                self._speak_whole(ERROR_TEXT, clock)
            finally:
                self.out.put_nowait(("turn_end", None))
                self.busy = False
                log.info("%s: turn %d processing %s ms", self.id, self.turn_count, clock.processing_ms)

    async def _agent_turn(self, text: str, clock: TurnClock) -> None:
        state = await self.agent.aget_state(self.config)
        spoke = False
        messages = [HumanMessage(text)]
        if not state.values.get("messages"):
            messages.insert(0, AIMessage(instructions.GREETING))
        payload: Any = {"messages": messages}
        # concern-begin: refill-guard
        # The guard asked the confirmation question on an earlier caller turn and the run is paused
        # in interrupt(). This caller turn is the answer: it is the resume value, and only a caller
        # turn ever resumes it, so the answer always comes from a later turn than the question.
        if state.interrupts:
            payload = Command(resume={"text": text, "turn": self.turn_count})
        # concern-end
        current: Optional[Message] = None
        current_id = None
        async for mode, data in self.agent.astream(payload, self.config,
                                                   stream_mode=["messages", "custom", "updates"]):
            if mode == "messages":
                chunk, meta = data
                if meta.get("langgraph_node") != "model":
                    continue
                if chunk.id != current_id:
                    self._finish(current)
                    current, current_id = None, chunk.id
                delta = chunk.text
                if delta:
                    current = current or Message(clock)
                    self._feed(current, delta)
                    spoke = True
                calls = getattr(chunk, "tool_call_chunks", None) or []
                if calls and not spoke:
                    self._speak_whole(FILLERS.get(calls[0].get("name") or "", "One moment."), clock)
                    spoke = True
            # concern-begin: refill-guard
            # What the guard asks to be spoken: the decline, a filler once a yes is accepted, and
            # the confirmation question from interrupt().
            elif mode == "custom" and isinstance(data, dict) and data.get("say"):
                self._finish(current)
                current = None
                self._speak_whole(data["say"], clock)
                spoke = True
            elif mode == "custom" and isinstance(data, dict) and data.get("confirmed") and not spoke:
                # The caller's yes was accepted and the request is being sent.
                self._speak_whole(FILLERS["confirmed"], clock)
                spoke = True
            elif mode == "updates" and isinstance(data, dict) and "__interrupt__" in data:
                self._finish(current)
                current = None
                for item in data["__interrupt__"]:
                    value = getattr(item, "value", None)
                    if isinstance(value, dict) and value.get("question"):
                        self._speak_whole(value["question"], clock)
            # concern-end
        self._finish(current)

    # -- speaking ----------------------------------------------------------------

    def _feed(self, message: Message, delta: str) -> None:
        message.buffer += delta
        sentences, message.buffer = split_sentences(message.buffer)
        for sentence in sentences:
            self._queue_sentence(message, sentence)

    def _finish(self, message: Optional[Message]) -> None:
        if message is None:
            return
        if message.buffer.strip():
            self._queue_sentence(message, message.buffer.strip())
            message.buffer = ""
        if message.parts:
            self.out.put_nowait(("bot", message))

    def _speak_whole(self, text: str, clock: TurnClock) -> None:
        message = Message(clock)
        self._queue_sentence(message, text)
        self.out.put_nowait(("bot", message))

    def _queue_sentence(self, message: Message, sentence: str) -> None:
        message.parts.append(sentence)
        message.clock.ready()
        # Synthesis starts now, while the model keeps streaming; the sender plays results in order.
        task = asyncio.create_task(self._synthesize(sentence))
        self.out.put_nowait(("speech", (task, message.clock)))

    async def _synthesize(self, text: str) -> tuple[bytes, dict]:
        began = time.monotonic()
        try:
            pcm = await self.tts.synthesize(text)
        except Exception as exc:
            log.error("%s: text-to-speech failed for %r: %s", self.id, text[:60], exc)
            return b"", {}
        # The vendor returns a whole WAV, so the first byte arrives with the last (as in the Rasa engine).
        done_ms = round((time.monotonic() - began) * 1000, 1)
        return pcm, {"tts_first_byte_latency_ms": done_ms, "tts_complete_latency_ms": done_ms}

    async def _send(self, frame: dict) -> None:
        await self.ws.send_text(json.dumps(frame))

    async def _marker(self, latency: Optional[dict] = None) -> None:
        marker = secrets.token_hex(8)
        self.unacked.add(marker)
        await self._send({"marker": marker, **({"latency": latency} if latency else {})})

    async def _sender(self) -> None:
        """The only writer after the handshake: audio, markers, and the events that follow them."""
        second = SAMPLE_RATE * 2
        while True:
            kind, item = await self.out.get()
            try:
                if kind == "speech":
                    task, clock = item
                    pcm, tts = await task
                    if not pcm:
                        continue
                    await self._marker()
                    for offset in range(0, len(pcm), second):
                        await self._send({"audio": base64.b64encode(pcm[offset:offset + second]).decode("ascii")})
                        if offset + second < len(pcm):
                            await self._marker()
                    await self._marker({"rasa_processing_latency_ms": clock.processing_ms or 0.0, **tts})
                elif kind == "bot":
                    self.conv.add("bot", " ".join(item.parts))
                elif kind == "turn_end":
                    self.conv.add("bot_turn_ended")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("%s: send failed: %s", self.id, exc)

    async def _silence_watch(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            if self.busy or not self.out.empty() or self.unacked or not self.turns.empty():
                continue
            quiet_since = max(self.last_caller_activity, self.last_playback_done)
            if time.time() - quiet_since >= SILENCE_TIMEOUT_S:
                self.last_playback_done = time.time()
                self._speak_whole(SILENCE_PROMPT, TurnClock(time.time()))
                self.out.put_nowait(("turn_end", None))
