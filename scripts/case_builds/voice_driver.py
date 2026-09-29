"""A scripted caller for Rasa's `browser_audio` voice channel. Stdlib only.

The harness runs under a bare `python3` (3.13+ has no `audioop`, and scripts/
takes no third-party packages), so this module carries its own RFC 6455
WebSocket client: text frames, client masking, ping/pong and close. That is
all the channel uses.

Protocol, as implemented by rasa-pro 3.21.0.dev5
(rasa/core/channels/voice_stream/browser_audio.py and voice_channel.py):

- Connect to `ws://<host>/webhooks/browser_audio/websocket`. When the channel
  config sets `external_sender_id_header`, that header on the upgrade request
  becomes the conversation's sender id, so the tracker, usage log and server
  log all join on the id the driver chose.
- The server sends `{"type": "handshake", "sample_rate": N}` first. Every
  frame after that is JSON text.
- Client to server: `{"audio": <base64 16-bit LE mono PCM at N Hz>}`,
  `{"text": <utterance>}` (skips speech-to-text) and `{"marker": <id>}`
  (playback acknowledgement).
- Server to client: `{"audio": ...}`, `{"marker": <hex>}` (start,
  intermediate and end markers; an end marker may carry
  `{"latency": {rasa_processing_latency_ms, tts_first_byte_latency_ms,
  tts_complete_latency_ms}}`) and `{"interruptPlayback": true}`.
- There is no end-of-bot-turn frame. The driver reads the end of a bot turn
  from the tracker (a new `bot_turn_ended` for every new user event), then
  waits for its emulated speaker to drain; without a tracker it falls back to
  a quiet window.

The caller streams continuously in real time, as a browser does: 20 ms
frames of the scripted utterance, and silence between turns and while the
bot talks. The emulated speaker plays received audio at the handshake rate
and acknowledges each marker once the audio before it has played, with the
legacy Inspector client's rule that a tick which plays nothing acks nothing.
"""

from __future__ import annotations

import array
import base64
import hashlib
import json
import math
import os
import re
import socket
import struct
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlsplit

FRAME_MS = 20
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
DEFAULT_SENDER_HEADER = "X-Rasa-Sender-Id"


# ----------------------------------------------------------------------------
# Minimal RFC 6455 framing and client
# ----------------------------------------------------------------------------

OP_CONT, OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA


class WebSocketClosed(Exception):
    pass


def encode_frame(opcode: int, payload: bytes, *, mask: bool) -> bytes:
    """One FIN frame. Clients must mask (RFC 6455 5.3); servers must not."""
    header = bytearray([0x80 | opcode])
    length = len(payload)
    mask_bit = 0x80 if mask else 0
    if length < 126:
        header.append(mask_bit | length)
    elif length < 1 << 16:
        header.append(mask_bit | 126)
        header += struct.pack("!H", length)
    else:
        header.append(mask_bit | 127)
        header += struct.pack("!Q", length)
    if not mask:
        return bytes(header) + payload
    key = os.urandom(4)
    masked = bytes(b ^ key[i % 4] for i, b in enumerate(payload)) if length < 4096 else _xor_fast(payload, key)
    return bytes(header) + key + masked


def _xor_fast(payload: bytes, key: bytes) -> bytes:
    n = len(payload)
    k = int.from_bytes((key * (n // 4 + 1))[:n], "big")
    return (int.from_bytes(payload, "big") ^ k).to_bytes(n, "big")


def _recv_exact(sock: Any, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise WebSocketClosed("connection closed")
        buf += chunk
    return bytes(buf)


def read_frame(sock: Any) -> tuple[bool, int, bytes]:
    """(fin, opcode, payload) of the next frame, unmasking when needed."""
    b0, b1 = _recv_exact(sock, 2)
    fin, opcode = bool(b0 & 0x80), b0 & 0x0F
    masked, length = bool(b1 & 0x80), b1 & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    key = _recv_exact(sock, 4) if masked else None
    payload = _recv_exact(sock, length) if length else b""
    if key:
        payload = _xor_fast(payload, key)
    return fin, opcode, payload


class _Prebuffered:
    """A socket's recv() that first returns bytes already read past the upgrade."""

    def __init__(self, sock: socket.socket, buffered: bytes) -> None:
        self.sock = sock
        self.buffered = buffered

    def recv(self, n: int) -> bytes:
        if self.buffered:
            chunk, self.buffered = self.buffered[:n], self.buffered[n:]
            return chunk
        return self.sock.recv(n)


def accept_key(client_key: str) -> str:
    return base64.b64encode(hashlib.sha1((client_key + WS_GUID).encode()).digest()).decode()


class WebSocketClient:
    """Blocking client: one thread may send while another receives."""

    def __init__(self, url: str, headers: Optional[dict] = None, timeout: float = 10.0) -> None:
        parts = urlsplit(url)
        if parts.scheme != "ws":
            raise ValueError("only ws:// is supported (the harness talks to a local server)")
        host, port = parts.hostname or "127.0.0.1", parts.port or 80
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        key = base64.b64encode(os.urandom(16)).decode()
        lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
            *[f"{k}: {v}" for k, v in (headers or {}).items()],
            "",
            "",
        ]
        self.sock.sendall("\r\n".join(lines).encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WebSocketClosed("server closed during the upgrade")
            response += chunk
        head, _, rest = response.partition(b"\r\n\r\n")
        status_line, *header_lines = head.decode("latin-1").split("\r\n")
        if " 101 " not in f"{status_line} ":
            raise WebSocketClosed(f"upgrade refused: {status_line}")
        got = {k.strip().lower(): v.strip() for k, v in (h.split(":", 1) for h in header_lines if ":" in h)}
        if got.get("sec-websocket-accept") != accept_key(key):
            raise WebSocketClosed("bad Sec-WebSocket-Accept")
        # The server may send its first frame in the same read as the upgrade
        # response; keep those bytes for the frame reader.
        self.reader = _Prebuffered(self.sock, rest)
        self.sock.settimeout(None)
        self._send_lock = threading.Lock()
        self.closed = False

    def send_text(self, text: str) -> None:
        self._send(OP_TEXT, text.encode())

    def _send(self, opcode: int, payload: bytes) -> None:
        if self.closed:
            raise WebSocketClosed("socket closed")
        frame = encode_frame(opcode, payload, mask=True)
        with self._send_lock:
            try:
                self.sock.sendall(frame)
            except OSError as exc:
                self.closed = True
                raise WebSocketClosed(str(exc)) from exc

    def recv_text(self) -> Optional[str]:
        """Next text message, or None once the server closed the connection."""
        parts: list[bytes] = []
        while True:
            try:
                fin, opcode, payload = read_frame(self.reader)
            except (WebSocketClosed, OSError):
                self.closed = True
                return None
            if opcode == OP_PING:
                try:
                    self._send(OP_PONG, payload)
                except WebSocketClosed:
                    return None
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                try:
                    self._send(OP_CLOSE, payload[:2])
                except WebSocketClosed:
                    pass
                self.closed = True
                return None
            if opcode in (OP_TEXT, OP_BINARY, OP_CONT):
                parts.append(payload)
                if fin:
                    return b"".join(parts).decode("utf-8", errors="replace")

    def close(self) -> None:
        if not self.closed:
            try:
                self._send(OP_CLOSE, struct.pack("!H", 1000))
            except WebSocketClosed:
                pass
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


# ----------------------------------------------------------------------------
# Caller audio
# ----------------------------------------------------------------------------


def caller_audio_name(voice: str, text: str) -> str:
    """Fixture file name for one caller line: the same voice and words share a file."""
    digest = hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()[:12]
    return f"{voice}-{digest}.wav"


def turn_audio_name(turn: dict, default_voice: str) -> str:
    return turn.get("audio") or caller_audio_name(turn.get("caller_voice") or default_voice, turn["user"])


def load_pcm16(path: Path) -> tuple[bytes, int]:
    """Mono 16-bit PCM bytes and the file's sample rate."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise ValueError(f"{path}: need 16-bit mono PCM")
        return w.readframes(w.getnframes()), w.getframerate()


def voiced_bounds(pcm: bytes, rate: int, dbfs: float = -40.0) -> tuple[int, int]:
    """First and last voiced sample (10 ms RMS above *dbfs*); (0, 0) if silent."""
    samples = array.array("h")
    samples.frombytes(pcm)
    hop = max(1, rate // 100)
    voiced = []
    for start in range(0, len(samples) - hop + 1, hop):
        window = samples[start:start + hop]
        rms = math.sqrt(sum(s * s for s in window) / hop) / 32768.0
        if 20 * math.log10(max(rms, 1e-9)) > dbfs:
            voiced.append(start)
    if not voiced:
        return 0, 0
    return voiced[0], voiced[-1] + hop


def has_sound(pcm: bytes) -> bool:
    return any(pcm)


# ----------------------------------------------------------------------------
# Emulated speaker
# ----------------------------------------------------------------------------


class Speaker:
    """Plays received bot audio in real time and acks markers as it drains.

    A marker is queued at the number of samples waiting to play when it
    arrives, and acked once those samples have played. As in the legacy
    Inspector client, a tick that plays nothing acks nothing, so a marker that
    arrives on an empty queue waits for the next audio, unless `prompt_ack`.
    """

    def __init__(self, rate: int, send: Callable[[str], None], prompt_ack: bool = False) -> None:
        self.rate = rate
        self.send = send
        self.prompt_ack = prompt_ack
        self.queued = 0
        self.marks: list[list] = []
        self.acked = 0
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def enqueue(self, pcm: bytes) -> None:
        with self.lock:
            self.queued += len(pcm) // 2

    def add_marker(self, marker: str) -> None:
        with self.lock:
            self.marks.append([marker, self.queued])

    def clear(self) -> None:
        with self.lock:
            self.queued = 0
            self.marks.clear()

    @property
    def drained(self) -> bool:
        with self.lock:
            return self.queued == 0

    @property
    def pending_markers(self) -> int:
        with self.lock:
            return len(self.marks)

    def run(self, tick: float = 0.01) -> None:
        last = time.monotonic()
        while not self.stop.is_set():
            time.sleep(tick)
            now = time.monotonic()
            due: list[str] = []
            with self.lock:
                played = min(self.queued, int((now - last) * self.rate))
                last = now
                if played <= 0 and not (self.prompt_ack and self.queued == 0):
                    continue
                self.queued -= played
                for m in self.marks:
                    m[1] -= played
                while self.marks and self.marks[0][1] <= 0:
                    due.append(self.marks.pop(0)[0])
            for marker in due:
                try:
                    self.send(json.dumps({"marker": marker}))
                    self.acked += 1
                except WebSocketClosed:
                    return


# ----------------------------------------------------------------------------
# Tracker reading
# ----------------------------------------------------------------------------


def _events(tracker: Optional[dict], kind: str) -> list[dict]:
    return [e for e in (tracker or {}).get("events", []) if e.get("event") == kind]


def turn_done_in_tracker(tracker: dict, users_before: int, ends_before: int) -> bool:
    """A new bot_turn_ended exists, and every new user event has its own."""
    users = len(_events(tracker, "user")) - users_before
    ends = len(_events(tracker, "bot_turn_ended")) - ends_before
    return ends >= 1 and ends >= users


# ----------------------------------------------------------------------------
# The driver
# ----------------------------------------------------------------------------


@dataclass
class TurnTimes:
    speech_on: Optional[float] = None
    speech_off: Optional[float] = None
    speech_off_epoch: Optional[float] = None
    first_marker: Optional[float] = None
    first_audio: Optional[float] = None
    first_audible: Optional[float] = None
    end_markers: list = field(default_factory=list)
    interrupts: int = 0
    bot_audio_samples: int = 0
    last_server_frame: float = 0.0


class BrowserAudioCall:
    """One call on the browser_audio channel. Used by the harness's driver."""

    def __init__(
        self,
        ws_url: str,
        sender_id: str,
        *,
        sender_header: str = DEFAULT_SENDER_HEADER,
        fetch_tracker: Optional[Callable[[str], dict]] = None,
        prompt_ack: bool = False,
        quiet_window_s: float = 2.5,
        settle_s: float = 0.6,
        turn_timeout_s: float = 90.0,
        tracker_poll_s: float = 0.25,
    ) -> None:
        self.ws_url = ws_url
        self.sender_id = sender_id
        self.sender_header = sender_header
        self.fetch_tracker = fetch_tracker
        self.prompt_ack = prompt_ack
        self.quiet_window_s = quiet_window_s
        self.settle_s = settle_s
        self.turn_timeout_s = turn_timeout_s
        self.tracker_poll_s = tracker_poll_s
        self.rate = 0
        self.frames_sent = 0
        self.lock = threading.Lock()
        self.mic: Optional[bytes] = None
        self.mic_pos = 0
        self.voiced = (0, 0)
        self.turn: Optional[TurnTimes] = None
        self.closed = threading.Event()
        self.threads: list[threading.Thread] = []
        self.unknown_frames = 0
        self.started = 0.0

    # -- lifecycle -----------------------------------------------------------

    def open(self, greeting_timeout_s: float = 30.0) -> dict:
        self.ws = WebSocketClient(self.ws_url, {self.sender_header: self.sender_id})
        self.ws.sock.settimeout(greeting_timeout_s)
        try:
            first = self.ws.recv_text()
        finally:
            self.ws.sock.settimeout(None)
        handshake = json.loads(first) if first else {}
        if handshake.get("type") != "handshake":
            raise RuntimeError(f"expected a handshake frame, got {first!r}")
        self.rate = int(handshake["sample_rate"])
        self.started = time.monotonic()
        self.speaker = Speaker(self.rate, self.ws.send_text, self.prompt_ack)
        self.greeting = TurnTimes(last_server_frame=time.monotonic())
        self.turn = self.greeting
        for target in (self._mic_pump, self._receiver, self.speaker.run):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self.threads.append(thread)
        # The greeting has no user event to pair with, so it is waited out on
        # audio: first sound, then the speaker drained and a quiet window.
        deadline = time.monotonic() + greeting_timeout_s
        while time.monotonic() < deadline and not self.closed.is_set():
            if self.greeting.first_audio and self.speaker.drained and \
                    time.monotonic() - self.greeting.last_server_frame >= self.quiet_window_s:
                break
            time.sleep(0.05)
        return {"sample_rate": self.rate, "greeting_audio_s": round(self.greeting.bot_audio_samples / self.rate, 2)}

    def close(self) -> dict:
        self.speaker.stop.set()
        self.ws.close()
        self.closed.set()
        for thread in self.threads:
            thread.join(timeout=2)
        return {
            "audio_seconds_sent": round(self.frames_sent * FRAME_MS / 1000, 2),
            "call_seconds": round(time.monotonic() - self.started, 2),
            "markers_acked": self.speaker.acked,
            "markers_unacked_at_close": self.speaker.pending_markers,
            "unknown_server_frames": self.unknown_frames,
        }

    # -- threads ---------------------------------------------------------------

    def _mic_pump(self) -> None:
        """Continuous real-time stream: utterance frames, else silence."""
        n = self.rate * FRAME_MS // 1000
        silence = b"\x00\x00" * n
        deadline = time.monotonic()
        while not self.closed.is_set():
            with self.lock:
                if self.mic is not None:
                    start = self.mic_pos
                    frame = self.mic[start * 2:(start + n) * 2]
                    self.mic_pos += n
                    now = time.monotonic()
                    on, off = self.voiced
                    turn = self.turn
                    if turn is not None and start <= on < start + n:
                        turn.speech_on = now + (on - start) / self.rate
                    if turn is not None and start <= off <= start + n:
                        turn.speech_off = now + (off - start) / self.rate
                        turn.speech_off_epoch = time.time() + (off - start) / self.rate
                    if len(frame) < n * 2:
                        frame += silence[: n * 2 - len(frame)]
                    if self.mic_pos * 2 >= len(self.mic):
                        self.mic = None
                else:
                    frame = silence
            try:
                self.ws.send_text(json.dumps({"audio": base64.b64encode(frame).decode("ascii")}))
            except WebSocketClosed:
                self.closed.set()
                return
            self.frames_sent += 1
            deadline += FRAME_MS / 1000
            time.sleep(max(0.0, deadline - time.monotonic()))

    def _receiver(self) -> None:
        while True:
            raw = self.ws.recv_text()
            if raw is None:
                break
            now = time.monotonic()
            try:
                msg = json.loads(raw)
            except ValueError:
                self.unknown_frames += 1
                continue
            turn = self.turn
            after = turn is not None and (turn is self.greeting or (turn.speech_off is not None and now >= turn.speech_off))
            if turn is not None:
                turn.last_server_frame = now
            if "audio" in msg:
                pcm = base64.b64decode(msg["audio"])
                self.speaker.enqueue(pcm)
                if after:
                    turn.bot_audio_samples += len(pcm) // 2
                    turn.first_audio = turn.first_audio or now
                    if turn.first_audible is None and has_sound(pcm):
                        turn.first_audible = now
            elif "marker" in msg:
                self.speaker.add_marker(msg["marker"])
                if after:
                    turn.first_marker = turn.first_marker or now
                    if msg.get("latency") and not (turn.end_markers and _same_latency(turn.end_markers[-1], msg["latency"])):
                        # Markers sent during pacing silence repeat the previous
                        # message's figures (the TTS metrics reset after pacing),
                        # so only a changed latency object is a new end marker.
                        turn.end_markers.append({"at_ms": _ms(now, turn.speech_off), **msg["latency"]})
            elif msg.get("interruptPlayback"):
                self.speaker.clear()
                if turn is not None:
                    turn.interrupts += 1
            else:
                self.unknown_frames += 1
        self.closed.set()

    # -- turns -------------------------------------------------------------------

    def _tracker(self) -> Optional[dict]:
        if self.fetch_tracker is None:
            return None
        try:
            return self.fetch_tracker(self.sender_id)
        except Exception:
            return None

    def say(self, *, pcm: Optional[bytes] = None, text: Optional[str] = None,
            think_s: float = 0.5) -> dict:
        """Speak one caller turn (audio, or text in dry-run) and wait for the reply."""
        time.sleep(think_s)
        before = self._tracker()
        users_before = len(_events(before, "user"))
        ends_before = len(_events(before, "bot_turn_ended"))
        bots_before = len(_events(before, "bot"))
        turn = TurnTimes(last_server_frame=time.monotonic())
        speech_s = 0.0
        if text is not None:
            with self.lock:
                self.turn = turn
                turn.speech_on = turn.speech_off = time.monotonic()
                turn.speech_off_epoch = time.time()
            self.ws.send_text(json.dumps({"text": text}))
        else:
            on, off = voiced_bounds(pcm, self.rate)
            speech_s = (off - on) / self.rate
            with self.lock:
                self.turn = turn
                self.voiced = (on, off)
                self.mic_pos = 0
                self.mic = pcm
            while True:
                with self.lock:
                    if self.mic is None:
                        break
                if self.closed.is_set():
                    break
                time.sleep(FRAME_MS / 1000)

        ended_by, tracker = self._wait_bot_turn(turn, users_before, ends_before)
        new_users = _events(tracker, "user")[users_before:]
        new_ends = _events(tracker, "bot_turn_ended")[ends_before:]
        new_bots = _events(tracker, "bot")[bots_before:]
        first = turn.first_audible or turn.first_audio
        return {
            "latency_ms": _ms(first, turn.speech_off),
            "voice": {
                "mode": "text" if text is not None else "audio",
                "speech_s": round(speech_s, 2),
                "speech_off_epoch": turn.speech_off_epoch,
                "eos_to_first_marker_ms": _ms(turn.first_marker, turn.speech_off),
                "eos_to_first_audio_ms": _ms(turn.first_audio, turn.speech_off),
                "eos_to_first_audible_ms": _ms(turn.first_audible, turn.speech_off),
                "end_markers": turn.end_markers,
                "bot_audio_s": round(turn.bot_audio_samples / self.rate, 2),
                "interrupts": turn.interrupts,
                "ended_by": ended_by,
                "markers_pending": self.speaker.pending_markers,
                "heard": [e.get("text") for e in new_users],
                "latency_breakdown": [(e.get("metadata") or {}).get("latency_breakdown") for e in new_ends],
            },
            "bot_messages": [{"text": e.get("text")} for e in new_bots],
        }

    def _wait_bot_turn(self, turn: TurnTimes, users_before: int, ends_before: int) -> tuple[str, Optional[dict]]:
        deadline = time.monotonic() + self.turn_timeout_s
        next_poll = 0.0
        tracker = None
        seen_done = None
        while time.monotonic() < deadline:
            if self.closed.is_set():
                return "closed", self._tracker()
            now = time.monotonic()
            quiet = now - turn.last_server_frame
            if self.fetch_tracker is not None and now >= next_poll:
                next_poll = now + self.tracker_poll_s
                polled = self._tracker()
                if polled is not None:
                    tracker = polled
                    if turn_done_in_tracker(tracker, users_before, ends_before):
                        seen_done = seen_done or now
                    else:
                        seen_done = None
            if seen_done is not None and self.speaker.drained and quiet >= self.settle_s:
                # Re-read once: a caller turn the ASR split in two gets a
                # second user event, which must be answered before moving on.
                tracker = self._tracker() or tracker
                if turn_done_in_tracker(tracker, users_before, ends_before):
                    return "tracker", tracker
                seen_done = None
            if self.fetch_tracker is None and turn.first_audio and self.speaker.drained \
                    and quiet >= self.quiet_window_s:
                return "quiet_window", tracker
            time.sleep(0.05)
        return "timeout", self._tracker() or tracker


LATENCY_KEYS = ("rasa_processing_latency_ms", "tts_first_byte_latency_ms", "tts_complete_latency_ms")


def _same_latency(a: dict, b: dict) -> bool:
    return all(a.get(k) == b.get(k) for k in LATENCY_KEYS)


def dedupe_latency_markers(markers: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in markers:
        if not (out and _same_latency(out[-1], m)):
            out.append(m)
    return out


def _ms(later: Optional[float], earlier: Optional[float]) -> Optional[float]:
    if later is None or earlier is None:
        return None
    return round((later - earlier) * 1000, 1)


# ----------------------------------------------------------------------------
# Speech-to-text checks
# ----------------------------------------------------------------------------

_UNITS = {
    "zero": 0, "oh": 0, "o": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
             "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
             "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
             "nineteenth": 19, "twentieth": 20, "thirtieth": 30}
_ORDINAL_SUFFIX_RE = re.compile(r"\b(\d+)(?:st|nd|rd|th)\b")


def _number_tokens(text: str) -> list:
    """Words, with each run of adjacent number groups as one list of groups."""
    words = re.findall(r"[a-z]+|\d+", _ORDINAL_SUFFIX_RE.sub(r"\1 _ord_", text.lower().replace("-", " ")))
    items: list = []
    run: list[str] = []

    def flush() -> None:
        if run:
            items.append(list(run))
            run.clear()

    i = 0
    while i < len(words):
        w = words[i]
        if w == "ord":
            flush()
        elif w.isdigit():
            run.append(w)
        elif w in _TENS:
            value = _TENS[w]
            nxt = words[i + 1] if i + 1 < len(words) else ""
            if nxt in _UNITS and 0 < _UNITS[nxt] < 10:
                i += 1
                run.append(str(value + _UNITS[nxt]))
            elif nxt in _ORDINALS and _ORDINALS[nxt] < 10:
                i += 1
                run.append(str(value + _ORDINALS[nxt]))
                flush()
            else:
                run.append(str(value))
        elif w in _UNITS and not (w in ("o", "oh") and not run):
            run.append(str(_UNITS[w]))
        elif w in _ORDINALS:
            run.append(str(_ORDINALS[w]))
            flush()
        elif w == "and" and run:
            pass
        else:
            flush()
            items.append(w)
        i += 1
    flush()
    return items


def number_runs(text: str) -> list[list[str]]:
    """Spoken and written numbers in *text*, as runs of adjacent digit groups.

    Each number word or digit string is one group: 'four four one seven' is
    ['4', '4', '1', '7'], 'nineteen eighty six' is ['19', '86'], 'fifty five
    oh two' is ['55', '0', '2'], '4417' is ['4417']. Adjacent groups form one
    run; any other word ends it. An ordinal ('fourteenth', '14th') ends its run,
    since a spoken date's day is followed by a separate year.
    """
    return [item for item in _number_tokens(text) if isinstance(item, list)]


def normalised_words(text: str) -> list[str]:
    """Lower-case words, with every number spelled out as single-digit tokens.

    'nineteen eighty-six', '1986' and '1 9 8 6' all become 1 9 8 6, so the
    word error rate counts a wrong digit as one error whichever way the
    transcript grouped or spelled the number.
    """
    out: list[str] = []
    for item in _number_tokens(text or ""):
        if isinstance(item, list):
            out.extend("".join(item))
        else:
            out.append(item)
    return out


def word_error_rate(reference: str, hypothesis: str) -> Optional[float]:
    """Word-level edit distance over reference length, after normalised_words."""
    ref, hyp = normalised_words(reference), normalised_words(hypothesis)
    if not ref:
        return None
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return round(prev[-1] / len(ref), 3)


def spoken_numbers_to_digits(text: str) -> list[str]:
    """Each number run joined into one digit string: 'nineteen eighty six' -> '1986'."""
    return ["".join(run) for run in number_runs(text)]


def _run_contains(run: list[str], token: str) -> bool:
    """True when a contiguous slice of whole groups spells *token*."""
    for i in range(len(run)):
        joined = ""
        for group in run[i:]:
            joined += group
            if joined == token:
                return True
            if len(joined) >= len(token):
                break
    return False


def check_tokens(heard: str, tokens: list[dict]) -> list[dict]:
    """Did the transcript carry each checked token?

    `exact`: the token appears verbatim in the raw transcript (case-insensitive,
    as a whole word). `normalised`: after spoken numbers become digits, for
    every kind except `name`; names are only ever checked exactly.
    """
    raw = (heard or "").lower()
    runs = number_runs(heard or "")
    results = []
    for spec in tokens:
        token = str(spec["token"])
        kind = spec.get("kind", "digits")
        pattern = r"(?<![\w])" + re.escape(token.lower()) + r"(?![\w])"
        exact = re.search(pattern, raw) is not None
        normalised = exact or (kind != "name" and any(_run_contains(run, token) for run in runs))
        results.append({"token": token, "kind": kind, "exact": exact, "normalised": normalised})
    return results
