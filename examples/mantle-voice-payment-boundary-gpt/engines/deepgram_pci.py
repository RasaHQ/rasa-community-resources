"""Rasa's built-in Deepgram engine, removing card details from every transcript.

Why. On a voice call the conversation record starts at speech-to-text: Rasa
writes each final transcript into the tracker as the caller's message, sends
it to the model, lets Mantle's memory read it and logs it. A caller who
starts reading a card number puts it in all four before any tool or prompt
can object (the case's failure). A prompt rule cannot help, because the
words are recorded before the model runs. Mantle declares an
``incoming_message`` hook, but on rasa-pro 3.21.0.dev5 nothing dispatches it
(see README), so it cannot help either.

What this changes. ``engine_event_to_asr_event`` passes every
``NewTranscript`` and ``UserIsSpeaking`` through ``lib.pci.redact`` before
Rasa sees it, so the tracker, the model request, memory and logs get
"[card details removed]" in place of the digits. The final transcript right
after one with a removal is checked for a card read in two breaths. Each
removal is logged as ``willowshop.pci_redaction`` with counts only, never the
text. Everything else is the built-in engine with its own config.

What it does not change. Deepgram still receives the caller's audio and
returns the words; that is the speech vendor's side of the boundary, which a
payments owner has to cover in the vendor agreement. Removing card details
from a record is not a payment-security certification.

The engine also sets ``lib.payments.REDACTION_FLAG`` in this process when it
is created, so the payment tools can refuse to start a payment on a server
whose voice channel does not remove card details (the case's
``recorder_excluded`` rule).
"""

from __future__ import annotations

import os
from typing import Any, List, Optional

import structlog

from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript, UserIsSpeaking
from rasa.core.channels.voice_stream.asr.deepgram import DeepgramASR

from lib.pci import redact
from lib.payments import REDACTION_FLAG, REDACTION_VALUE

structlogger = structlog.get_logger()


class DeepgramRedactingCardDetails(DeepgramASR):
    """``DeepgramASR`` whose transcripts never carry card numbers, security codes or expiry dates."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._after_removal = False
        self.removals = 0
        os.environ[REDACTION_FLAG] = REDACTION_VALUE

    def engine_event_to_asr_event(self, e: Any) -> Optional[Any]:
        event = super().engine_event_to_asr_event(e)
        if isinstance(event, NewTranscript) and event.text:
            text, removed = redact(event.text, continuation=self._after_removal)
            self._after_removal = removed > 0
            if removed:
                self.removals += removed
                structlogger.info("willowshop.pci_redaction", kind="final", spans=removed,
                                  call_removals=self.removals)
            return NewTranscript(text=text)
        if isinstance(event, UserIsSpeaking) and event.text:
            text, removed = redact(event.text, continuation=self._after_removal)
            return UserIsSpeaking(text=text) if removed else event
        return event
