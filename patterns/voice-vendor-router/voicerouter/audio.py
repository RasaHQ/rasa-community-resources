"""Turning whatever a vendor returns into what Rasa's channel expects.

Rasa asks for one of three formats — 24 kHz or 48 kHz linear PCM16, or 8 kHz
G.711 mu-law for telephony. Vendors return whatever they like: raw PCM at their
own sample rate, or a WAV file with a header on the front.

Every adapter in `providers/` calls `to_rasa_audio` and stops worrying about it.
Getting this wrong does not raise — it produces audio at the wrong speed or
pitch, which is a bug you hear rather than one you catch, so it lives in one
tested place instead of in five adapters.
"""

from __future__ import annotations

import audioop
import struct
from typing import Any

from rasa.core.channels.voice_stream.audio_bytes import (
    AudioEncoding,
    AudioFormat,
    RasaAudioBytes,
)

_PCM16_WIDTH = 2


def strip_wav_header(data: bytes) -> tuple[bytes, int | None]:
    """Return (pcm_payload, sample_rate) for a RIFF/WAVE blob.

    Non-WAV input is passed straight back with no sample rate, so this is safe
    to call on anything. The `data` chunk is located properly rather than by
    assuming the usual 44-byte header: vendors that add a LIST/INFO chunk would
    otherwise leak metadata bytes into the audio as a burst of noise.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data, None

    sample_rate: int | None = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        (chunk_size,) = struct.unpack("<I", data[offset + 4 : offset + 8])
        body = offset + 8
        if chunk_id == b"fmt " and body + 16 <= len(data):
            sample_rate = struct.unpack("<I", data[body + 4 : body + 8])[0]
        elif chunk_id == b"data":
            return data[body : body + chunk_size], sample_rate
        offset = body + chunk_size + (chunk_size % 2)  # chunks are word-aligned
    return data, sample_rate


def pcm16_to_format(pcm: bytes, source_rate: int, target: AudioFormat) -> bytes:
    """Resample mono PCM16 and encode it for the target format."""
    if not pcm:
        return b""
    if source_rate != target.sample_rate:
        pcm, _ = audioop.ratecv(
            pcm, _PCM16_WIDTH, 1, source_rate, target.sample_rate, None
        )
    if target.encoding == AudioEncoding.MULAW:
        return audioop.lin2ulaw(pcm, _PCM16_WIDTH)
    return pcm


def to_rasa_audio(
    raw: bytes, source_rate: int, target: AudioFormat, is_wav: bool = False
) -> RasaAudioBytes:
    """Vendor bytes in, channel-ready audio out.

    `source_rate` is what the vendor was asked to produce. When `is_wav` is set
    and the blob really carries a header, the rate declared in that header wins:
    a vendor quietly returning 22 kHz for a 16 kHz request should not become a
    pitch bug.
    """
    if is_wav:
        raw, declared = strip_wav_header(raw)
        if declared:
            source_rate = declared
    return RasaAudioBytes(pcm16_to_format(raw, source_rate, target), format=target)

class PcmStreamConverter:
    """Convert a *stream* of PCM16 chunks, correctly, across chunk boundaries.

    Two things go wrong if you convert each HTTP chunk independently, and
    neither shows up on a single-shot test:

    1. **Split frames.** Chunks arrive on arbitrary byte boundaries, so a chunk
       can end mid-sample. `audioop` rejects that outright with "not a whole
       number of frames". The leftover byte is carried to the next chunk.

    2. **Resampler discontinuity.** `audioop.ratecv` returns a state that must
       be fed back in for the next call. Passing `None` each time restarts the
       filter on every chunk, which does not raise — it just adds a click at
       every boundary, several times a second.

    One converter per utterance; a fresh one starts clean state.
    """

    def __init__(self, source_rate: int, target: AudioFormat) -> None:
        self._source_rate = source_rate
        self._target = target
        self._remainder = b""
        self._ratecv_state: Any = None

    def feed(self, chunk: bytes) -> bytes:
        """Convert one chunk, holding back any partial trailing frame."""
        data = self._remainder + chunk
        usable = len(data) - (len(data) % _PCM16_WIDTH)
        self._remainder = data[usable:]
        data = data[:usable]
        if not data:
            return b""

        if self._source_rate != self._target.sample_rate:
            data, self._ratecv_state = audioop.ratecv(
                data, _PCM16_WIDTH, 1, self._source_rate,
                self._target.sample_rate, self._ratecv_state,
            )
        if self._target.encoding == AudioEncoding.MULAW:
            return audioop.lin2ulaw(data, _PCM16_WIDTH)
        return data

    def flush(self) -> bytes:
        """Nothing useful remains: a lone byte is not a sample."""
        self._remainder = b""
        return b""
