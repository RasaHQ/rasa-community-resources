# concern: voice-loop
"""The voice loop for the CrewAI version: Rasa's browser_audio protocol, written by hand.

    uv run --locked python server.py --port 5010

This single CrewAI agent uses application-written voice transport. Everything in
``../shared/web/PROTOCOL.md`` is here, around the ``cedar_speech``
Speechmatics clients and ``agent.Conversation``:

- ``WS /webhooks/browser_audio/websocket``: the handshake, 24 kHz PCM16 audio
  frames in, ``{"text"}`` turns, marker acknowledgements; audio and markers out.
- End of turn: Speechmatics' ``EndOfUtterance`` (0.7 s of silence) gives one
  final transcript per caller turn; each final is one agent turn.
- Sentence chunking: streamed model text is cut at sentence ends and each
  sentence is synthesised as soon as it is complete, ahead of playback.
- Markers: start, one per second of audio, and an end marker with the three
  latency fields on every bot message.
- Fillers: when tools finish before anything was said in the turn, a short
  fixed phrase plays while the next model call runs.
- Silence check-in: 30 s after the agent's audio has played with no caller
  speech, a fixed prompt.
- Barge-in: not implemented. Caller audio keeps flowing to speech-to-text
  while the agent speaks, and a transcript that arrives then is answered
  after the current turn.
- ``GET /conversations/{id}/events`` and ``GET /health``.
"""

from __future__ import annotations

from cedar_speech.router import create_asr, create_tts

import argparse
import asyncio
import base64
import json
import os
import re
import time
import uuid
from typing import Optional

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from cedar_clinic import instructions
from cedar_speech import config

import agent as cedar

WS_PATH = "/webhooks/browser_audio/websocket"
SENDER_HEADER = "x-rasa-sender-id"
SENDER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
RATE = config.SAMPLE_RATE
CHUNK_BYTES = RATE * 2 // 5  # 200 ms of audio per frame
SECOND_BYTES = RATE * 2
SILENCE_TIMEOUT_S = 30.0  # as Rasa's silence_timeout
SILENCE_PROMPT = "Are you still there? I can help you send a refill request."
FILLERS = {
    "verify_patient": "Thanks, one moment while I check.",
    "select_medication": "Let me find that on your record.",
    "send_refill_request": "Okay, one moment.",
    "check_request_status": "Let me check on that request.",
    "route_clinical_question": "One moment.",
}
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

#: conversation id -> events, the shape PROTOCOL.md section 5 fixes.
EVENTS: dict[str, list[dict]] = {}
TTS = create_tts()


def log(*parts: object) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def add_event(conversation_id: str, event: str, **fields: object) -> None:
    EVENTS.setdefault(conversation_id, []).append({"event": event, "timestamp": time.time(), **fields})


class Chunker:
    """Cuts streamed text into sentences for text-to-speech."""

    def __init__(self) -> None:
        self.buffer = ""

    def feed(self, delta: str) -> list[str]:
        self.buffer += delta
        parts = SENTENCE_END.split(self.buffer)
        self.buffer = parts.pop()
        return [p.strip() for p in parts if p.strip()]

    def flush(self) -> list[str]:
        rest, self.buffer = self.buffer.strip(), ""
        return [rest] if rest else []


class Call:
    """One browser_audio connection."""

    def __init__(self, ws: WebSocket, conversation_id: str) -> None:
        self.ws = ws
        self.cid = conversation_id
        self.open = True
        self.send_lock = asyncio.Lock()
        self.turns: asyncio.Queue = asyncio.Queue()
        self.asr: Optional[SpeechmaticsASR] = None
        self.unacked: dict[str, bool] = {}  # marker -> is the last end marker of a turn
        self.played_at: Optional[float] = None  # when the agent's last turn finished playing
        self.last_speech = time.monotonic()
        self.busy = False

    async def send(self, frame: dict) -> None:
        if not self.open:
            return
        async with self.send_lock:
            try:
                await self.ws.send_text(json.dumps(frame))
            except Exception:
                self.open = False

    async def run(self) -> None:
        await self.send({"type": "handshake", "sample_rate": RATE})
        tasks = [asyncio.create_task(self.turn_loop()), asyncio.create_task(self.silence_loop())]
        try:
            self.asr = await create_asr(RATE).open()
            tasks.append(asyncio.create_task(self.asr_loop()))
        except Exception as exc:  # typed turns still work
            log(self.cid, "speech-to-text unavailable:", exc)
        try:
            await self.receive_loop()
        finally:
            self.open = False
            for task in tasks[1:]:
                task.cancel()
            if self.asr is not None:
                await self.asr.close()
            await cedar.conversation(self.cid).close()
            tasks[0].cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            # Release a pending caller confirmation and stop the voice loop.
            await self.turns.put(None)
            log(self.cid, "hung up")

    # -- input ------------------------------------------------------------------

    async def receive_loop(self) -> None:
        while True:
            try:
                raw = await self.ws.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                return
            try:
                frame = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(frame, dict):
                continue
            if "audio" in frame and self.asr is not None:
                try:
                    await self.asr.send_audio(base64.b64decode(frame["audio"]))
                except Exception as exc:
                    log(self.cid, "speech-to-text send failed:", exc)
                    self.asr = None
            elif frame.get("text"):
                self.caller_turn(str(frame["text"]))
            elif "marker" in frame:
                if self.unacked.pop(str(frame["marker"]), False):
                    self.played_at = time.monotonic()

    async def asr_loop(self) -> None:
        try:
            async for event in self.asr.events():
                self.last_speech = time.monotonic()
                if event.final:
                    self.caller_turn(event.text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log(self.cid, "speech-to-text stopped:", exc)

    def caller_turn(self, text: str) -> None:
        """A final transcript (or typed turn): log the user event now, answer it in order."""
        add_event(self.cid, "user", text=text)
        self.last_speech = time.monotonic()
        self.played_at = None
        self.turns.put_nowait((text, time.monotonic()))

    # -- turns --------------------------------------------------------------------

    async def turn_loop(self) -> None:
        await self.bot_turn([("fixed", instructions.GREETING, "greeting")], time.monotonic(), None)
        while True:
            item = await self.turns.get()
            if item is None:
                return
            text, heard_at = item
            log(self.cid, "caller:", text)
            try:
                await self.bot_turn(None, heard_at, text)
            except Exception as exc:
                log(self.cid, "turn failed:", repr(exc))
                add_event(self.cid, "bot_turn_ended", error=repr(exc))

    async def bot_turn(self, fixed: Optional[list], heard_at: float, text: Optional[str]) -> None:
        """Run the agent on one caller turn (or speak fixed messages) and speak the result."""
        self.busy = True
        speech: asyncio.Queue = asyncio.Queue()
        turn = {"heard_at": heard_at, "first_ready": None, "spoken": 0}
        speaker = asyncio.create_task(self.speaker(speech, turn))

        def message(sentences: list[str], msg: dict) -> None:
            for sentence in sentences:
                if turn["first_ready"] is None:
                    turn["first_ready"] = time.monotonic()
                speech.put_nowait(("sentence", msg, sentence, asyncio.create_task(self.synthesize(sentence))))

        def whole(text_: str, source: str) -> None:
            msg = {"id": uuid.uuid4().hex}
            add_event(self.cid, "bot", text=text_, metadata={"source": source})
            turn["spoken"] += 1
            message(Chunker().feed(text_ + " ") or [text_], msg)
            speech.put_nowait(("end", msg))

        try:
            if fixed is not None:
                for _, text_, source in fixed:
                    whole(text_, source)
            else:
                chunker, msg = Chunker(), None
                async for say in cedar.conversation(self.cid).turn(text):
                    if say.kind == "delta":
                        msg = msg or {"id": uuid.uuid4().hex}
                        message(chunker.feed(say.text), msg)
                    elif say.kind == "end":
                        msg = msg or {"id": uuid.uuid4().hex}
                        message(chunker.flush(), msg)
                        add_event(self.cid, "bot", text=say.text.strip(), metadata={"source": "model"})
                        turn["spoken"] += 1
                        speech.put_nowait(("end", msg))
                        msg = None
                    elif say.kind == "fixed":
                        whole(say.text, say.source)
                    elif say.kind == "tools" and say.source == "ok" and not turn["spoken"] and say.text in FILLERS:
                        whole(FILLERS[say.text], "filler")
        finally:
            speech.put_nowait(None)
            await speaker
            add_event(self.cid, "bot_turn_ended")
            self.busy = False

    async def synthesize(self, sentence: str) -> tuple[bytes, float, float]:
        began = time.monotonic()
        pcm = await TTS.synthesize(sentence) if self.open else b""
        return pcm, began, time.monotonic()

    async def speaker(self, speech: asyncio.Queue, turn: dict) -> None:
        """Send each message's audio in order: start marker, audio, a marker per second, end marker."""
        state: dict[str, dict] = {}
        last_end: Optional[str] = None
        while True:
            item = await speech.get()
            if item is None:
                break
            if item[0] == "sentence":
                _, msg, sentence, task = item
                try:
                    pcm, began, done = await task
                except Exception as exc:
                    log(self.cid, "text-to-speech failed:", exc)
                    continue
                s = state.setdefault(msg["id"], {"began": began, "first": done, "sent": 0})
                if s["sent"] == 0:
                    await self.marker()
                for i in range(0, len(pcm), CHUNK_BYTES):
                    chunk = pcm[i:i + CHUNK_BYTES]
                    await self.send({"audio": base64.b64encode(chunk).decode("ascii")})
                    before, s["sent"] = s["sent"], s["sent"] + len(chunk)
                    if s["sent"] // SECOND_BYTES > before // SECOND_BYTES:
                        await self.marker()
                s["done"] = max(done, s.get("done", done))
            else:
                s = state.get(item[1]["id"])
                if not s:
                    continue
                first_ready = turn["first_ready"] or s["began"]
                last_end = await self.marker({
                    "rasa_processing_latency_ms": round((first_ready - turn["heard_at"]) * 1000, 1),
                    "tts_first_byte_latency_ms": round((s["first"] - s["began"]) * 1000, 1),
                    "tts_complete_latency_ms": round((s["done"] - s["began"]) * 1000, 1),
                })
        if last_end is not None:
            self.unacked[last_end] = True

    async def marker(self, latency: Optional[dict] = None) -> str:
        marker = uuid.uuid4().hex[:16]
        self.unacked[marker] = False
        await self.send({"marker": marker, **({"latency": latency} if latency else {})})
        return marker

    async def silence_loop(self) -> None:
        """A fixed check-in after 30 s of silence once the agent's audio has played."""
        while True:
            await asyncio.sleep(0.5)
            now = time.monotonic()
            if self.busy or self.played_at is None or not self.turns.empty():
                continue
            if now - max(self.played_at, self.last_speech) >= SILENCE_TIMEOUT_S:
                log(self.cid, "silence check-in")
                self.played_at = None
                await self.bot_turn([("fixed", SILENCE_PROMPT, "silence")], now, None)


async def browser_audio(ws: WebSocket) -> None:
    sender = ws.headers.get(SENDER_HEADER, "")
    conversation_id = sender if SENDER_RE.match(sender) else f"inspect-{uuid.uuid4()}"
    await ws.accept()
    log(conversation_id, "connected")
    await Call(ws, conversation_id).run()


async def events(request: Request) -> JSONResponse:
    return JSONResponse({"events": EVENTS.get(request.path_params["conversation_id"], [])})


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


app = Starlette(routes=[
    WebSocketRoute(WS_PATH, browser_audio),
    Route("/conversations/{conversation_id}/events", events),
    Route("/health", health),
])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5010")))
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning", ws="websockets-sansio")


if __name__ == "__main__":
    main()
