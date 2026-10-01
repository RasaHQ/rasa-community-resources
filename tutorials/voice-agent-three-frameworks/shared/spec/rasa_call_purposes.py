"""Start Rasa with each model call labelled by what Mantle made it for. Runs in the Rasa venv.

    uv run --locked python ../shared/spec/rasa_call_purposes.py run --enable-api -p 5005

A Rasa-only diagnostic for the comparison (test equipment; counts for no
framework). It does what ``scripts/case_builds/usage_launcher.py`` does (the
LiteLLM usage logger) and also wraps the Mantle functions that ask for a
model call (table below) so each sets a context variable naming its purpose
for as long as it runs, and wraps ``rasa.mantle.llm.client.LLMClient``'s
``acompletion`` and ``acompletion_streaming`` to read it. A context variable
rather than the call stack, because Mantle awaits the completion inside
``run_cancellable``, in another task; tasks inherit the variable. For every
call it appends one JSON line to ``RASA_CALL_PURPOSES_LOG``:

    {"ts_start", "ts_end", "sender_id", "purpose", "streamed",
     "tools_offered", "tool_calls", "text_chars", "prompt_tokens", "completion_tokens"}

Purposes, from the Mantle function on the stack (rasa-pro 3.21.0.dev5):

| purpose | Mantle function |
|---|---|
| ``orchestrator`` | ``Orchestrator._call_main_llm_with_empty_retry`` (one main-loop iteration: the model picks tools and/or text) |
| ``rephrase`` | ``Orchestrator._rephrase_and_send`` (a response template reworded by the model) |
| ``confirm_rephrase`` | ``Orchestrator._run_confirm_rephrase_call`` |
| ``fact_discovery`` | ``ContextExtractor.discover_facts`` (after a skill switch, off the reply path) |
| ``completion_judge`` | ``CompletionJudge.judge`` |
| ``other`` | a call made outside all of these |

Nothing in a request or response is changed, and no prompt or response
content is written: tool names, counts and lengths only.
"""

from __future__ import annotations

import contextvars
import functools
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts" / "case_builds"))

import usage_launcher  # noqa: E402

LOG = os.environ.get("RASA_CALL_PURPOSES_LOG")
_lock = threading.Lock()

_purpose: contextvars.ContextVar[str] = contextvars.ContextVar("mantle_llm_purpose", default="other")

#: (module, class, method) -> purpose
TARGETS = [
    ("rasa.mantle.orchestration.orchestrator", "Orchestrator", "_call_main_llm_with_empty_retry", "orchestrator"),
    ("rasa.mantle.orchestration.orchestrator", "Orchestrator", "_rephrase_and_send", "rephrase"),
    ("rasa.mantle.orchestration.orchestrator", "Orchestrator", "_run_confirm_rephrase_call", "confirm_rephrase"),
    ("rasa.mantle.memory.discovery.extractor", "ContextExtractor", "discover_facts", "fact_discovery"),
    ("rasa.mantle.orchestration.skill_completion.completion_judge", "CompletionJudge", "judge", "completion_judge"),
]


def _labelled(method, purpose: str):
    @functools.wraps(method)
    async def wrapper(*args, **kwargs):
        token = _purpose.set(purpose)
        try:
            return await method(*args, **kwargs)
        finally:
            _purpose.reset(token)

    return wrapper


def _write(row: dict) -> None:
    if not LOG:
        return
    with _lock, open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _sender() -> str | None:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        pass
    try:
        import structlog

        return structlog.contextvars.get_contextvars().get("conversation_id")
    except Exception:
        return None


def _wrap(method, streamed: bool):
    async def wrapper(self, messages, *args, **kwargs):
        purpose = _purpose.get()
        tools = kwargs.get("tools") if "tools" in kwargs else (args[0] if args else None)
        started = time.time()
        response = None
        try:
            response = await method(self, messages, *args, **kwargs)
            return response
        finally:
            usage = getattr(response, "usage", None)
            _write({
                "ts_start": round(started, 6),
                "ts_end": round(time.time(), 6),
                "sender_id": _sender(),
                "purpose": purpose,
                "streamed": streamed,
                "tools_offered": len(tools or []),
                "tool_calls": [getattr(tc, "tool_name", None) for tc in (getattr(response, "tool_calls", None) or [])],
                "text_chars": len((response.response_text() or "") if response is not None else ""),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "ok": response is not None,
            })

    return wrapper


def install() -> None:
    import importlib

    usage_launcher.install()
    from rasa.mantle.llm import client

    for module_name, class_name, method_name, purpose in TARGETS:
        cls = getattr(importlib.import_module(module_name), class_name)
        setattr(cls, method_name, _labelled(getattr(cls, method_name), purpose))

    client.LLMClient.acompletion = _wrap(client.LLMClient.acompletion, streamed=False)
    client.LLMClient.acompletion_streaming = _wrap(client.LLMClient.acompletion_streaming, streamed=True)


if __name__ == "__main__":
    install()
    from rasa.__main__ import main

    sys.argv = ["rasa", *sys.argv[1:]]
    main()
