"""NeuTTS-2E on Metal: local text-to-speech with no Python model stack.

    tts:
      name: voicerouter.providers.neutts_native.NeuTTSNative
      runtime_dir: ../../patterns/voice-vendor-router/native/neutts/build
      models_dir: ../../patterns/voice-vendor-router/native/neutts/models
      language_map:
        en:
          voice: sophie

The Python `neutts` package cannot be installed next to rasa-pro (it needs a
newer numpy than rasa-pro allows) and pulls in torch. This engine uses no
part of it. It drives two native programs that `native/neutts/build.sh`
builds from pinned sources:

- `llama-server` from Neuphonic's llama.cpp fork, running the
  `neutts-2e-Q4_0.gguf` backbone on the GPU through Metal. It turns text into
  NeuCodec speech codes (`<|speech_N|>` tokens, 50 per second of audio) and
  stays loaded between turns, listening on 127.0.0.1 only.
- `neucodec_decoder`, a small C++ program on ONNX Runtime that turns codes
  into 24 kHz audio with Neuphonic's int8 decoder, also kept loaded, spoken
  to over its stdin and stdout.

Both are started once per Rasa process, on the first call, and shared by
every call after it. Nothing here opens a connection to anything but
127.0.0.1, and neither program is given a network address.

**Streaming.** Codes are decoded while the backbone is still generating, in
chunks, the way NeuTTS's own `infer_stream` does it: each chunk is decoded
with up to 50 frames of look-back context and 5 of look-ahead, and chunks
are joined with a short linear cross-fade. The first audio is ready after
`first_chunk_frames + lookforward_frames` codes rather than after the whole
sentence. The chunk constants default to NeuTTS's.

**What it needs.** The prompt is NeuTTS-2E's: the speaker's reference text,
then the text to speak, then the speaker's reference codes. `voice` in the
language map names a speaker whose `<voice>.codes` and `<voice>.txt` are in
`models_dir` (`prepare_models.py` writes `sophie`). There is no numpy here:
audio is handled with `array` and `struct`.

Licences: the backbone is under the NeuTTS Open License 1.0, which limits
commercial use by organisations above 5 million USD annual revenue; the
decoder is Apache 2.0. See `native/neutts/README.md`.
"""

from __future__ import annotations

import array
import asyncio
import atexit
import hashlib
import json
import os
import re
import socket
import struct
import subprocess
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Sequence, Tuple

import structlog
from rasa.core.channels.voice_stream.audio_bytes import AudioFormat, RasaAudioBytes
from rasa.core.channels.voice_stream.tts.tts_engine import (
    TTSEngine,
    TTSEngineConfig,
    TTSError,
    TTSLanguageMapEntry,
)

from voicerouter.audio import PcmStreamConverter

logger = structlog.get_logger(__name__)

#: NeuCodec's output rate and frame size: 50 frames a second at 24 kHz.
NEUTTS_SAMPLE_RATE = 24000
HOP_SAMPLES = 480

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_NATIVE = _PACKAGE_ROOT / "native" / "neutts"
_SPEECH_RE = re.compile(r"<\|speech_(\d+)\|>")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_END_TOKEN = "<|SPEECH_GENERATION_END|>"
_EMOTIONS = ("angry", "disgusted", "fearful", "happy", "neutral", "sad", "surprised")


class NeuTTSNativeConfig(TTSEngineConfig):
    #: Folder holding `bin/llama-server`, `bin/neucodec_decoder` and `lib/`.
    runtime_dir: Optional[str] = None
    #: Folder holding the backbone, the decoder and the speaker files.
    models_dir: Optional[str] = None
    backbone_file: Optional[str] = None
    decoder_file: Optional[str] = None
    #: Use a llama-server that is already running instead of starting one.
    server_url: Optional[str] = None
    #: Check the model files against `models.lock` before the first call.
    verify_models: Optional[bool] = None
    gpu_layers: Optional[int] = None
    context_tokens: Optional[int] = None
    decoder_threads: Optional[int] = None
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    #: A fixed seed makes the same text come out the same way every time.
    seed: Optional[int] = None
    #: One of NeuTTS-2E's emotion tags; `neutral` sends none.
    emotion: Optional[str] = None
    first_chunk_frames: Optional[int] = None
    chunk_frames: Optional[int] = None
    lookback_frames: Optional[int] = None
    lookforward_frames: Optional[int] = None
    overlap_frames: Optional[int] = None
    #: Longer text is split at sentence ends into parts of about this length.
    max_segment_chars: Optional[int] = None
    #: Rewrite numerals as words before synthesis (default on). NeuTTS-2E does
    #: not read digits: "R-Q-6-1-5-0" came out as babble in every take.
    spell_numbers: Optional[bool] = None
    startup_timeout: Optional[float] = None


# ----------------------------------------------------------------------------
# Pure helpers: prompt, segmentation, streaming reassembly. No I/O.
# ----------------------------------------------------------------------------


def normalise_text(text: str) -> str:
    """NeuTTS's own normalisation: curly quotes to straight, then NFKC."""
    return unicodedata.normalize("NFKC", text.translate(_QUOTES)).strip()


_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SPACED_DIGITS_RE = re.compile(r"(?<![\d.])\d(?:[ -]\d(?![\d.]))+")
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+)(?:\.(\d+))?(?![\w])")


def _cardinal(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else f"-{_ONES[n % 10]}")
    rest = n % 100
    return f"{_ONES[n // 100]} hundred" + ("" if rest == 0 else f" {_cardinal(rest)}")


def spell_numbers(text: str) -> str:
    """Numerals as words, for a model that cannot read digits.

    Digits spaced out one by one ("6 1 5 0", "6-1-5-0") and numbers of four
    digits or more are read digit by digit, as references and phone numbers
    are said; numbers below 1,000 become cardinals ("10" -> "ten"); a decimal
    is read "zero point five".
    """
    text = _SPACED_DIGITS_RE.sub(lambda m: " ".join(_ONES[int(d)] for d in re.findall(r"\d", m.group(0))), text)

    def number(m: "re.Match[str]") -> str:
        whole, frac = m.group(1), m.group(2)
        words = " ".join(_ONES[int(d)] for d in whole) if len(whole) >= 4 else _cardinal(int(whole))
        if frac:
            words += " point " + " ".join(_ONES[int(d)] for d in frac)
        return words

    return _NUMBER_RE.sub(number, text)


def build_prompt(ref_text: str, ref_codes: Sequence[int], text: str, emotion: Optional[str] = None) -> str:
    """The NeuTTS-2E prompt for one piece of text (BPE input, fixed speaker)."""
    ref_text, text = normalise_text(ref_text), normalise_text(text)
    joined = f"{ref_text} {text}" if not emotion or emotion == "neutral" else f"{ref_text}<|{emotion.upper()}|>{text}"
    codes = "".join(f"<|speech_{c}|>" for c in ref_codes)
    return f"<|TEXT_PROMPT_START|>{joined}<|TEXT_PROMPT_END|><|SPEECH_GENERATION_START|>{codes}"


def split_segments(text: str, max_chars: int) -> List[str]:
    """Sentences, packed into parts of at most ``max_chars`` where possible.

    NeuTTS generates one prompt at a time and its quality drifts on long
    inputs; a sentence is the natural unit. A single sentence longer than the
    limit is kept whole rather than cut mid-phrase.
    """
    text = normalise_text(text)
    if not text:
        return []
    parts: List[str] = []
    for sentence in _SENTENCE_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if parts and len(parts[-1]) + 1 + len(sentence) <= max_chars:
            parts[-1] = f"{parts[-1]} {sentence}"
        else:
            parts.append(sentence)
    return parts


def max_speech_tokens(text: str, context_tokens: int, prompt_tokens_estimate: int) -> int:
    """A generation cap: about 8 codes per character, within the context left."""
    budget = max(150, 8 * len(text) + 100)
    return max(50, min(budget, context_tokens - prompt_tokens_estimate - 8))


def float_to_pcm16(samples: Sequence[float]) -> bytes:
    """[-1, 1] floats to little-endian 16-bit PCM, clipped, without numpy."""
    out = array.array("h", (int(round((1.0 if s > 1.0 else -1.0 if s < -1.0 else s) * 32767.0)) for s in samples))
    if out.itemsize != 2:  # pragma: no cover - every CPython platform has 2-byte shorts
        raise TTSError("array('h') is not 16-bit on this platform")
    return out.tobytes() if _LITTLE_ENDIAN else _byteswapped(out)


_LITTLE_ENDIAN = struct.pack("=H", 1) == b"\x01\x00"


def _byteswapped(values: array.array) -> bytes:  # pragma: no cover - big-endian hosts only
    copy = array.array("h", values)
    copy.byteswap()
    return copy.tobytes()


def _triangle(length: int) -> List[float]:
    """NeuTTS's overlap-add weight: a triangle over the chunk, never zero."""
    return [0.5 - abs((j + 1) / (length + 1) - 0.5) for j in range(length)]


DecodeFn = Callable[[List[int], int, int], Sequence[float]]


class StreamAssembler:
    """Turns a growing list of speech codes into gap-free audio, chunk by chunk.

    Chunk ``i`` covers ``chunk_frames`` new frames. It is decoded together
    with up to ``lookback`` frames before it (the speaker's reference codes
    count, so even the first chunk has context) and ``lookforward`` after,
    and sliced to its own frames plus ``2 * overlap`` frames of tail. The tail
    is cross-faded into the head of the next chunk with NeuTTS's triangular
    weights, so audio is released only up to the start of that tail.
    """

    def __init__(
        self,
        ref_codes: Sequence[int],
        decode: DecodeFn,
        first_chunk_frames: int = 25,
        chunk_frames: int = 25,
        lookback: int = 50,
        lookforward: int = 5,
        overlap: int = 1,
    ) -> None:
        self._codes: List[int] = list(ref_codes)
        self._decoded_to = len(self._codes)
        self._decode = decode
        self._first = first_chunk_frames
        self._chunk = chunk_frames
        self._lookback = lookback
        self._lookforward = lookforward
        self._overlap = overlap
        self._tail: List[float] = []
        self._tail_weights: List[float] = []
        self.chunks_decoded = 0
        self.generated = 0

    def _next_chunk_frames(self) -> int:
        return self._first if self.chunks_decoded == 0 else self._chunk

    def push(self, codes: Sequence[int]) -> List[bytes]:
        """Add generated codes; return PCM16 for every chunk now complete."""
        self._codes.extend(codes)
        self.generated += len(codes)
        out: List[bytes] = []
        while len(self._codes) - self._decoded_to >= self._next_chunk_frames() + self._lookforward:
            frames = self._next_chunk_frames()
            start = max(self._decoded_to - self._lookback - self._overlap, 0)
            end = self._decoded_to + frames + self._lookforward + self._overlap
            offset = (self._decoded_to - start) * HOP_SAMPLES
            span = (frames + 2 * self._overlap) * HOP_SAMPLES
            audio = list(self._decode(self._codes[start:end], offset, offset + span))
            out.append(self._emit(audio, frames * HOP_SAMPLES, final=False))
            self._decoded_to += frames
            self.chunks_decoded += 1
        return [chunk for chunk in out if chunk]

    def finish(self) -> bytes:
        """Decode what is left after generation stopped, and release all audio."""
        if len(self._codes) > self._decoded_to:
            start = max(self._decoded_to - self._lookback - self._overlap, 0)
            offset = (self._decoded_to - start) * HOP_SAMPLES
            audio = list(self._decode(self._codes[start:], offset, 0xFFFFFFFF))
            self._decoded_to = len(self._codes)
            self.chunks_decoded += 1
            return self._emit(audio, len(audio), final=True)
        tail, self._tail, self._tail_weights = self._tail, [], []
        return float_to_pcm16(tail)

    def _emit(self, audio: List[float], release: int, final: bool) -> bytes:
        weights = _triangle(len(audio)) if audio else []
        mixed = list(audio)
        n = min(len(self._tail), len(mixed))
        for j in range(n):
            wt, wa = self._tail_weights[j], weights[j]
            mixed[j] = (wt * self._tail[j] + wa * mixed[j]) / (wt + wa)
        leftover_tail = self._tail[n:]
        if final:
            released = mixed + leftover_tail
            self._tail, self._tail_weights = [], []
        else:
            released = mixed[:release]
            self._tail, self._tail_weights = mixed[release:], weights[release:]
        return float_to_pcm16(released)


# ----------------------------------------------------------------------------
# The native runtime: two child processes, shared by every call in a process.
# ----------------------------------------------------------------------------


def _read_lock(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                values[key] = value
    return values


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class NativeRuntime:
    """llama-server and neucodec_decoder, started once and kept warm."""

    _instances: Dict[Tuple[Any, ...], "NativeRuntime"] = {}
    _instances_lock = threading.Lock()

    def __init__(self, runtime_dir: Path, models_dir: Path, backbone: Path, decoder: Path,
                 server_url: Optional[str], gpu_layers: int, context_tokens: int,
                 decoder_threads: int, verify_models: bool, startup_timeout: float) -> None:
        self.runtime_dir = runtime_dir
        self.models_dir = models_dir
        self.backbone = backbone
        self.decoder_model = decoder
        self.server_url = server_url
        self.gpu_layers = gpu_layers
        self.context_tokens = context_tokens
        self.decoder_threads = decoder_threads
        self.verify_models = verify_models
        self.startup_timeout = startup_timeout
        self._server: Optional[subprocess.Popen] = None
        self._decoder: Optional[subprocess.Popen] = None
        self._decode_lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._speakers: Dict[str, Tuple[str, List[int]]] = {}
        self.started = False
        self.startup_seconds: Optional[float] = None

    @classmethod
    def shared(cls, **kwargs: Any) -> "NativeRuntime":
        key = tuple(sorted((k, str(v)) for k, v in kwargs.items()))
        with cls._instances_lock:
            if key not in cls._instances:
                cls._instances[key] = cls(**kwargs)
            return cls._instances[key]

    # -- startup --------------------------------------------------------------

    def _check_models(self) -> None:
        missing = [p for p in (self.backbone, self.decoder_model) if not p.is_file()]
        if missing:
            raise TTSError(
                f"NeuTTSNative: model file(s) not found: {', '.join(map(str, missing))}. "
                "Run native/neutts/prepare_models.py."
            )
        if not self.verify_models:
            return
        lock = _read_lock(_DEFAULT_NATIVE / "models.lock")
        for part, path in (("backbone", self.backbone), ("decoder", self.decoder_model)):
            size, sha = lock.get(f"{part}.bytes"), lock.get(f"{part}.sha256")
            if not size or not sha:
                raise TTSError("NeuTTSNative: models.lock is missing; cannot verify the model files")
            if path.stat().st_size != int(size) or _sha256(path) != sha:
                raise TTSError(f"NeuTTSNative: {path.name} does not match models.lock (size or SHA-256)")

    def _binary(self, name: str) -> Path:
        path = self.runtime_dir / "bin" / name
        if not os.access(path, os.X_OK):
            raise TTSError(f"NeuTTSNative: {path} not found. Build it with native/neutts/build.sh.")
        return path

    def _start_server(self) -> None:
        port = _free_port()
        args = [
            str(self._binary("llama-server")), "-m", str(self.backbone),
            "--host", "127.0.0.1", "--port", str(port),
            "-c", str(self.context_tokens), "-ngl", str(self.gpu_layers), "-np", "1",
            # Speech codes are special tokens: without --special the server
            # returns an empty string for every one of them.
            "--special", "--no-ui", "--offline", "--log-disable",
            # No host-memory prompt cache: every NeuTTS prompt carries new
            # text before the speaker codes, so a saved prompt is never
            # reused, and with the default 8 GiB limit the cache grew the
            # server to 3.3 GB over one 23-call run.
            "--cache-ram", "0",
        ]
        self._server = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
        self.server_url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + self.startup_timeout
        import urllib.request

        while time.monotonic() < deadline:
            if self._server.poll() is not None:
                raise TTSError(f"NeuTTSNative: llama-server exited with {self._server.returncode} at startup")
            try:
                with urllib.request.urlopen(f"{self.server_url}/health", timeout=1) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(0.1)
        raise TTSError("NeuTTSNative: llama-server did not become healthy in time")

    def _start_decoder(self) -> None:
        self._decoder = subprocess.Popen(
            [str(self._binary("neucodec_decoder")), str(self.decoder_model), "--serve",
             "--threads", str(self.decoder_threads)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        assert self._decoder.stderr is not None
        line = self._decoder.stderr.readline().decode(errors="replace")
        if "ready" not in line:
            raise TTSError(f"NeuTTSNative: neucodec_decoder did not start: {line.strip()}")
        # Keep draining stderr so the child never blocks on a full pipe.
        threading.Thread(target=self._drain, args=(self._decoder.stderr,), daemon=True).start()

    @staticmethod
    def _drain(stream: Any) -> None:
        for _ in iter(stream.readline, b""):
            pass

    def start(self) -> None:
        with self._start_lock:
            if self.started:
                return
            began = time.monotonic()
            self._check_models()
            if not self.server_url:
                self._start_server()
            self._start_decoder()
            atexit.register(self.close)
            self.started = True
            self.startup_seconds = round(time.monotonic() - began, 3)
            logger.info("neutts_native.started", server_url=self.server_url,
                        startup_s=self.startup_seconds, backbone=self.backbone.name)

    def speaker(self, name: str) -> Tuple[str, List[int]]:
        if name not in self._speakers:
            codes_path = self.models_dir / f"{name}.codes"
            text_path = self.models_dir / f"{name}.txt"
            if not codes_path.is_file() or not text_path.is_file():
                raise TTSError(f"NeuTTSNative: speaker '{name}' needs {codes_path} and {text_path}")
            codes = [int(c) for c in codes_path.read_text().split()]
            self._speakers[name] = (text_path.read_text(encoding="utf-8").strip(), codes)
        return self._speakers[name]

    # -- decoding ---------------------------------------------------------------

    def decode(self, codes: List[int], start: int, end: int) -> array.array:
        """Codes to float samples [start:end), through the resident decoder."""
        if self._decoder is None or self._decoder.poll() is not None:
            raise TTSError("NeuTTSNative: neucodec_decoder is not running")
        request = b"NCDQ" + struct.pack("<III", len(codes), start, end) + struct.pack(f"<{len(codes)}i", *codes)
        with self._decode_lock:
            assert self._decoder.stdin is not None and self._decoder.stdout is not None
            self._decoder.stdin.write(request)
            self._decoder.stdin.flush()
            header = self._decoder.stdout.read(12)
            if len(header) != 12 or header[:4] != b"NCDA":
                raise TTSError("NeuTTSNative: neucodec_decoder closed or sent a bad reply")
            status, count = struct.unpack("<II", header[4:])
            if status != 0:
                message = self._decoder.stdout.read(count).decode(errors="replace")
                raise TTSError(f"NeuTTSNative: decode failed: {message}")
            payload = self._decoder.stdout.read(count * 4)
        samples = array.array("f")
        samples.frombytes(payload)
        if not _LITTLE_ENDIAN:  # pragma: no cover
            samples.byteswap()
        return samples

    def close(self) -> None:
        for proc in (self._decoder, self._server):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:  # pragma: no cover
                    proc.kill()
        self.started = False


# ----------------------------------------------------------------------------
# The Rasa engine.
# ----------------------------------------------------------------------------


class NeuTTSNative(TTSEngine[NeuTTSNativeConfig]):
    """Rasa TTS engine over the native NeuTTS runtime. No credentials, no network."""

    required_env_vars = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._runtime: Optional[NativeRuntime] = None
        self._session: Any = None
        #: Timings of the most recent utterance, for benchmarks and logs.
        self.last_timings: Dict[str, Any] = {}

    @classmethod
    def name(cls) -> str:
        return "neutts-native"

    def _path(self, value: Optional[str], default: Path) -> Path:
        return Path(value).expanduser().resolve() if value else default

    def _runtime_for_config(self) -> NativeRuntime:
        c = self.config
        models = self._path(c.models_dir, _DEFAULT_NATIVE / "models")
        return NativeRuntime.shared(
            runtime_dir=self._path(c.runtime_dir, _DEFAULT_NATIVE / "build"),
            models_dir=models,
            backbone=models / (c.backbone_file or "neutts-2e-Q4_0.gguf"),
            decoder=models / (c.decoder_file or "model.onnx"),
            server_url=c.server_url,
            gpu_layers=99 if c.gpu_layers is None else c.gpu_layers,
            context_tokens=c.context_tokens or 2048,
            decoder_threads=c.decoder_threads or 4,
            verify_models=True if c.verify_models is None else c.verify_models,
            startup_timeout=c.startup_timeout or 60.0,
        )

    async def connect(self, config: Optional[NeuTTSNativeConfig] = None) -> None:
        if self._runtime is None:
            self._runtime = self._runtime_for_config()
        if not self._runtime.started:
            await asyncio.to_thread(self._runtime.start)
        if self._session is None or self._session.closed:
            import aiohttp

            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_read=30))

    async def close_connection(self) -> None:
        # The runtime stays warm for the next call; only this call's HTTP
        # session to the local server is closed.
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _speaker_name(self) -> str:
        voice = getattr(self, "current_language_config", None)
        return (voice.voice if voice is not None and voice.voice else None) or "sophie"

    async def _generate(self, prompt: str, n_predict: int) -> AsyncIterator[List[int]]:
        """Stream speech codes from llama-server as they are generated."""
        c = self.config
        body: Dict[str, Any] = {
            "prompt": prompt,
            "n_predict": n_predict,
            "temperature": 1.0 if c.temperature is None else c.temperature,
            "top_k": c.top_k or 50,
            "stop": [_END_TOKEN],
            "stream": True,
            "cache_prompt": True,
        }
        if c.seed is not None:
            body["seed"] = c.seed
        assert self._runtime is not None and self._session is not None
        async with self._session.post(f"{self._runtime.server_url}/completion", json=body) as response:
            if response.status != 200:
                raise TTSError(f"NeuTTSNative: llama-server returned HTTP {response.status}")
            pending = ""
            async for raw in response.content:
                line = raw.decode(errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                pending += event.get("content", "")
                # A code is complete only once its closing "|>" has arrived.
                cut = pending.rfind("|>")
                if cut >= 0:
                    complete, pending = pending[: cut + 2], pending[cut + 2 :]
                    codes = [int(n) for n in _SPEECH_RE.findall(complete)]
                    if codes:
                        yield codes
                if event.get("stop"):
                    self.last_timings["server"] = event.get("timings")
                    self.last_timings["stop_type"] = event.get("stop_type")
                    break

    async def synthesize(self, text: str, config: Optional[NeuTTSNativeConfig] = None) -> AsyncIterator[RasaAudioBytes]:
        await self.connect()
        assert self._runtime is not None
        c = self.config
        ref_text, ref_codes = self._runtime.speaker(self._speaker_name())
        converter = PcmStreamConverter(NEUTTS_SAMPLE_RATE, self.audio_format)
        emotion = c.emotion if c.emotion in _EMOTIONS else None
        began = time.monotonic()
        first_audio: Optional[float] = None
        samples_out = 0
        decode_s = 0.0

        def timed_decode(codes: List[int], start: int, end: int) -> array.array:
            nonlocal decode_s
            t0 = time.monotonic()
            result = self._runtime.decode(codes, start, end)  # type: ignore[union-attr]
            decode_s += time.monotonic() - t0
            return result

        spoken = spell_numbers(text) if c.spell_numbers is not False else text
        segments = split_segments(spoken, c.max_segment_chars or 220)
        for segment in segments:
            assembler = StreamAssembler(
                ref_codes, timed_decode,
                first_chunk_frames=c.first_chunk_frames or 25,
                chunk_frames=c.chunk_frames or 25,
                lookback=50 if c.lookback_frames is None else c.lookback_frames,
                lookforward=5 if c.lookforward_frames is None else c.lookforward_frames,
                overlap=1 if c.overlap_frames is None else c.overlap_frames,
            )
            prompt = build_prompt(ref_text, ref_codes, segment, emotion)
            n_predict = max_speech_tokens(segment, self._runtime.context_tokens, len(ref_codes) + 2 * len(segment) + 40)
            pieces: List[bytes] = []
            async for codes in self._generate(prompt, n_predict):
                pieces = await asyncio.to_thread(assembler.push, codes)
                for pcm in pieces:
                    audio = converter.feed(pcm)
                    if audio:
                        if first_audio is None:
                            first_audio = time.monotonic() - began
                        samples_out += len(pcm) // 2
                        yield RasaAudioBytes(audio, format=self.audio_format)
            pcm = await asyncio.to_thread(assembler.finish)
            audio = converter.feed(pcm)
            if audio:
                if first_audio is None:
                    first_audio = time.monotonic() - began
                samples_out += len(pcm) // 2
                yield RasaAudioBytes(audio, format=self.audio_format)
        total = time.monotonic() - began
        audio_s = samples_out / NEUTTS_SAMPLE_RATE
        self.last_timings.update({
            "chars": len(text), "segments": len(segments),
            "first_audio_s": None if first_audio is None else round(first_audio, 4),
            "total_s": round(total, 4), "audio_s": round(audio_s, 3),
            "decode_s": round(decode_s, 4),
            "rtf": round(total / audio_s, 4) if audio_s else None,
        })
        logger.info("neutts_native.synthesized", **{k: v for k, v in self.last_timings.items() if k != "server"})
        if samples_out == 0:
            raise TTSError("NeuTTSNative: generation produced no speech codes")

    def engine_bytes_to_rasa_audio_bytes(self, chunk: bytes) -> RasaAudioBytes:
        return RasaAudioBytes(chunk, format=self.audio_format)

    @staticmethod
    def get_default_config(rasa_language: str) -> NeuTTSNativeConfig:
        return NeuTTSNativeConfig(
            timeout=60,
            language_map={rasa_language: TTSLanguageMapEntry(voice="sophie")},
        )

    @classmethod
    def from_config_dict(cls, config: Any, format: AudioFormat, rasa_language: str,
                         additional_languages: Optional[List[str]] = None) -> "NeuTTSNative":
        return cls(
            rasa_language=rasa_language, format=format,
            config=NeuTTSNativeConfig.model_validate(config or {}),
            additional_languages=additional_languages,
        )
