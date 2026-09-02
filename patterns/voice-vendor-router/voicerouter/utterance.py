"""Not every sentence is worth the same voice.

An agent says two very different kinds of thing. "One moment", "got it",
"let me check that" are filler: short, repeated thousands of times a day, and
nobody is listening closely. "Transferring four hundred pounds to Sam Rivera,
shall I go ahead?" is a disclosure: said once, load-bearing, and the one the
caller will replay in their head afterwards.

Routing both to the same provider is a decision, usually an unexamined one.
Sending filler to a cheap or local voice and keeping the premium provider for
the lines that matter is the single largest cost lever in a voice agent, and
nothing in Rasa can express it — a channel has one TTS engine.

Classification is deliberately dumb: length, and an optional list of patterns.
An LLM call to decide how to say a three-word acknowledgement would cost more
than the synthesis it is trying to economise on.

    policy:
      utterance_classes:
        filler:
          max_chars: 32
          patterns: ["^(ok|okay|got it|one moment|sure)\\\\b"]
          prefer: [neutts-local, deepgram]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_CLASS = "default"


@dataclass
class UtteranceClass:
    name: str
    max_chars: Optional[int] = None
    patterns: List[re.Pattern] = field(default_factory=list)
    #: Provider labels to try first for this class, in order.
    prefer: List[str] = field(default_factory=list)

    def matches(self, text: str) -> bool:
        stripped = text.strip()
        if self.max_chars is not None and len(stripped) > self.max_chars:
            return False
        if self.patterns and not any(p.search(stripped) for p in self.patterns):
            return False
        # A class with neither rule matches nothing; requiring at least one
        # avoids a typo silently capturing every utterance.
        return self.max_chars is not None or bool(self.patterns)

    @classmethod
    def from_dict(cls, name: str, raw: Dict[str, Any]) -> "UtteranceClass":
        unknown = set(raw) - {"max_chars", "patterns", "prefer"}
        if unknown:
            raise ValueError(
                f"utterance class {name!r} has unknown key(s): "
                f"{', '.join(sorted(unknown))}. Supported: max_chars, patterns, prefer."
            )
        if "max_chars" not in raw and not raw.get("patterns"):
            raise ValueError(
                f"utterance class {name!r} needs `max_chars` or `patterns`; "
                f"otherwise it would match nothing."
            )
        return cls(
            name=name,
            max_chars=int(raw["max_chars"]) if "max_chars" in raw else None,
            patterns=[re.compile(p, re.I) for p in (raw.get("patterns") or [])],
            prefer=list(raw.get("prefer") or []),
        )


@dataclass
class UtterancePolicy:
    classes: List[UtteranceClass] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]]) -> "UtterancePolicy":
        if not raw:
            return cls()
        # Declaration order is priority order: the first matching class wins,
        # so a narrow class can be placed above a broad one.
        return cls(classes=[UtteranceClass.from_dict(n, c) for n, c in raw.items()])

    def classify(self, text: str) -> str:
        for klass in self.classes:
            if klass.matches(text):
                return klass.name
        return DEFAULT_CLASS

    def preferred(self, text: str) -> List[str]:
        """Provider labels to try first for this utterance, if any."""
        for klass in self.classes:
            if klass.matches(text):
                return klass.prefer
        return []
