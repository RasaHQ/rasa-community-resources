"""The clinic's own record of every tool call, for framework-neutral checks.

The shared conversation spec judges all three versions of the agent by this
log, never by a framework's tracker or trace. Every call through
``cedar_clinic.tools`` appends one entry:

    {"seq": 7, "ts": 1790000000.123, "conversation_id": "rasa-normal-lisinopril-...",
     "kind": "tool", "name": "send_refill_request",
     "args": {...what the model supplied...},
     "state": {...what the framework supplied from its own state...},
     "result": {...the full result...}}

``kind`` is ``tool`` for a model-facing tool and ``confirmation`` for
``record_confirmation``, which a framework calls from its confirmation step.
A call that raised has ``is_error: true`` and ``result.error``.

Entries go to memory and, when ``CEDAR_AUDIT_LOG`` names a file, to that file
as JSON lines. The variable is read at the first write, so a server may set it
after import. Appends are serialised with a lock and written whole, one line
per entry, so concurrent conversations never interleave within a line.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

ENV_VAR = "CEDAR_AUDIT_LOG"


class AuditLog:
    def __init__(self, path: Optional[str | Path] = None) -> None:
        self._explicit_path = Path(path) if path else None
        self._lock = threading.Lock()
        self._entries: list[dict] = []
        self._seq = 0

    @property
    def path(self) -> Optional[Path]:
        if self._explicit_path is not None:
            return self._explicit_path
        value = os.environ.get(ENV_VAR, "").strip()
        return Path(value) if value else None

    def record(self, conversation_id: str, kind: str, name: str, *, args: dict, result: Any,
               state: Optional[dict] = None, is_error: bool = False) -> dict:
        with self._lock:
            self._seq += 1
            entry = {
                "seq": self._seq,
                "ts": round(time.time(), 6),
                "conversation_id": conversation_id,
                "kind": kind,
                "name": name,
                "args": args,
                "state": state or {},
                "result": result,
                "is_error": is_error,
            }
            self._entries.append(entry)
            path = self.path
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, default=str) + "\n")
        return entry

    def entries(self, conversation_id: Optional[str] = None) -> list[dict]:
        with self._lock:
            rows = list(self._entries)
        return [e for e in rows if conversation_id is None or e["conversation_id"] == conversation_id]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


def read_log(path: str | Path, conversation_id: Optional[str] = None) -> list[dict]:
    """Entries from an audit file, optionally for one conversation, in write order."""
    path = Path(path)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if conversation_id is None or entry.get("conversation_id") == conversation_id:
            rows.append(entry)
    return rows


#: The process-wide log every tool call goes to.
AUDIT = AuditLog()
