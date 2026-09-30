# concern: voice-adapter
"""16-bit PCM helpers: WAV unwrapping and resampling, as the Rasa engine does them.

``audioop`` is in the standard library up to Python 3.12 and in the
``audioop-lts`` package from 3.13 under the same name.
"""

from __future__ import annotations

import audioop
import base64
import struct
from typing import Optional


def strip_wav_header(data: bytes) -> tuple[bytes, Optional[int]]:
    """(pcm_payload, sample_rate) for a RIFF/WAVE blob; other input passes through.

    The data chunk is found by walking the chunks, not by assuming a 44-byte
    header. Speechmatics writes a streaming WAV whose data-chunk size is a
    placeholder, so the payload is sliced to the end of the blob.
    """
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data, None
    sample_rate: Optional[int] = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset: offset + 4]
        (chunk_size,) = struct.unpack("<I", data[offset + 4: offset + 8])
        body = offset + 8
        if chunk_id == b"fmt " and body + 16 <= len(data):
            sample_rate = struct.unpack("<I", data[body + 4: body + 8])[0]
        elif chunk_id == b"data":
            return data[body: body + chunk_size], sample_rate
        offset = body + chunk_size + (chunk_size % 2)
    return data, sample_rate


def wav_to_pcm(raw: bytes, source_rate: int, target_rate: int) -> bytes:
    """A vendor WAV (or raw PCM at source_rate) to 16-bit mono PCM at target_rate."""
    pcm, declared = strip_wav_header(raw)
    source_rate = declared or source_rate
    pcm = pcm[: len(pcm) - len(pcm) % 2]
    if pcm and source_rate != target_rate:
        pcm, _ = audioop.ratecv(pcm, 2, 1, source_rate, target_rate, None)
    return pcm


def b64_pcm(pcm16: bytes) -> str:
    """The browser_audio wire encoding of a chunk: base64 of 16-bit LE mono PCM."""
    return base64.b64encode(pcm16).decode("ascii")


def pcm_from_b64(data: str) -> bytes:
    return base64.b64decode(data)


def frames(pcm16: bytes, sample_rate: int, ms: int = 20) -> list[bytes]:
    """Split PCM into fixed frames (the last may be short)."""
    step = sample_rate * ms // 1000 * 2
    return [pcm16[i:i + step] for i in range(0, len(pcm16), step)]
