"""Run `rasa` with a LiteLLM usage logger attached. Runs inside the agent's venv.

The case-build harness starts the agent through this file instead of the
`rasa` entry point:

    uv run --locked python scripts/case_builds/usage_launcher.py run --enable-api

Rasa sends every model call through LiteLLM (a provider with no dedicated
Rasa client, such as `gemini`, goes to LiteLLM directly). A LiteLLM
`CustomLogger` therefore sees each completion with the provider's own usage
block and LiteLLM's cost calculation. This logger appends one JSON line per
call to the file named by CASE_BUILD_USAGE_LOG:

- tokens exactly as the provider reported them (prompt, completion, the
  reasoning share of completion, cached prompt tokens);
- `response_cost` as LiteLLM computed it from its bundled price map, or null
  when LiteLLM has no price for the model (the harness then reports cost as
  unknown rather than estimating);
- the conversation id, read from Mantle's turn context when the call happens
  inside a turn;
- for Gemini requests, how many `thoughtSignature` parts were sent back and how
  many were LiteLLM's placeholder rather than a real signature.

Nothing here changes a request or a response. Key values are never logged.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from typing import Any

LOG_PATH = os.environ.get("CASE_BUILD_USAGE_LOG")
# base64 of b"skip_thought_signature_validator": the placeholder LiteLLM
# inserts when a Gemini 3 request replays a function call without its real
# signature (litellm_core_utils/prompt_templates/factory.py).
DUMMY_THOUGHT_SIGNATURE = "c2tpcF90aG91Z2h0X3NpZ25hdHVyZV92YWxpZGF0b3I="
THOUGHT_SEPARATOR = "__thought__"

_lock = threading.Lock()


def _write(record: dict) -> None:
    if not LOG_PATH:
        return
    line = json.dumps(record, default=str)
    with _lock, open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _sender_id() -> tuple[str | None, str]:
    """The conversation a call belongs to, and where that came from.

    Main-loop calls run inside Mantle's turn context. Side-channel calls, such
    as fact discovery after a skill change, run after the turn but still carry
    Rasa's structlog `conversation_id` context.
    """
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id, "turn_context"
    except Exception:
        pass
    try:
        import structlog

        conversation = structlog.contextvars.get_contextvars().get("conversation_id")
        if conversation:
            return str(conversation), "structlog_context"
    except Exception:
        pass
    return None, "unknown"


def _get(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _signature_counts(kwargs: dict) -> dict:
    """Count thought signatures in the provider request and in the messages."""
    body = (kwargs.get("additional_args") or {}).get("complete_input_dict") or {}
    sent = dummy = function_calls = 0
    for content in body.get("contents", []) if isinstance(body, dict) else []:
        for part in content.get("parts", []) or []:
            if "function_call" in part or "functionCall" in part:
                function_calls += 1
            signature = part.get("thoughtSignature") or part.get("thought_signature")
            if signature:
                sent += 1
                dummy += signature == DUMMY_THOUGHT_SIGNATURE
    replayed = with_signature_in_id = 0
    for message in kwargs.get("messages") or []:
        for call in _get(message, "tool_calls") or []:
            replayed += 1
            with_signature_in_id += THOUGHT_SEPARATOR in str(_get(call, "id") or "")
    return {
        "request_function_call_parts": function_calls,
        "request_thought_signatures": sent,
        "request_placeholder_signatures": dummy,
        "replayed_tool_calls": replayed,
        "replayed_tool_call_ids_with_signature": with_signature_in_id,
    }


def _usage_record(kwargs: dict, response: Any, start: Any, end: Any, ok: bool) -> dict:
    usage = _get(response, "usage")
    completion_details = _get(usage, "completion_tokens_details")
    prompt_details = _get(usage, "prompt_tokens_details")
    choices = _get(response, "choices") or []
    first = choices[0] if choices else None
    message = _get(first, "message")
    tool_calls = _get(message, "tool_calls") or []
    returned_ids = [str(_get(c, "id") or "") for c in tool_calls]
    try:
        latency_ms = (end - start).total_seconds() * 1000
    except Exception:
        latency_ms = None
    sender_id, sender_source = _sender_id()
    record = {
        "kind": "llm_call",
        "ok": ok,
        "logged_at": time.time(),
        "sender_id": sender_id,
        "sender_source": sender_source,
        "model": kwargs.get("model"),
        "provider": kwargs.get("custom_llm_provider"),
        "response_model": _get(response, "model"),
        "latency_ms": latency_ms,
        "prompt_tokens": _get(usage, "prompt_tokens"),
        "completion_tokens": _get(usage, "completion_tokens"),
        "total_tokens": _get(usage, "total_tokens"),
        "reasoning_tokens": _get(completion_details, "reasoning_tokens"),
        "cached_prompt_tokens": _get(prompt_details, "cached_tokens"),
        "response_cost_usd": kwargs.get("response_cost"),
        "finish_reason": _get(first, "finish_reason"),
        "returned_tool_calls": [str(_get(_get(c, "function"), "name")) for c in tool_calls],
        "returned_tool_call_ids_with_signature": sum(THOUGHT_SEPARATOR in i for i in returned_ids),
        "returned_text_chars": len(_get(message, "content") or ""),
        **_signature_counts(kwargs),
    }
    if not ok:
        record["error"] = str(kwargs.get("exception") or response)[:500]
    return record


def install() -> None:
    import litellm
    from litellm.integrations.custom_logger import CustomLogger

    class CaseBuildUsageLogger(CustomLogger):
        async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
            _write(_usage_record(kwargs, response_obj, start_time, end_time, True))

        async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
            _write(_usage_record(kwargs, response_obj, start_time, end_time, False))

        def log_success_event(self, kwargs, response_obj, start_time, end_time):
            _write(_usage_record(kwargs, response_obj, start_time, end_time, True))

        def log_failure_event(self, kwargs, response_obj, start_time, end_time):
            _write(_usage_record(kwargs, response_obj, start_time, end_time, False))

    litellm.callbacks.append(CaseBuildUsageLogger())

    # Record the price LiteLLM will charge against, so the report can show
    # where every cost figure came from.
    model = os.environ.get("CASE_BUILD_PRICE_MODEL")
    if model:
        entry = litellm.model_cost.get(model) or {}
        _write(
            {
                "kind": "pricing",
                "model": model,
                "litellm_version": _version("litellm"),
                "rasa_pro_version": _version("rasa-pro"),
                "input_cost_per_token": entry.get("input_cost_per_token"),
                "output_cost_per_token": entry.get("output_cost_per_token"),
                "cache_read_input_token_cost": entry.get("cache_read_input_token_cost"),
                "input_cost_per_token_above_200k_tokens": entry.get(
                    "input_cost_per_token_above_200k_tokens"
                ),
                "output_cost_per_token_above_200k_tokens": entry.get(
                    "output_cost_per_token_above_200k_tokens"
                ),
                "local_cost_map": os.environ.get("LITELLM_LOCAL_MODEL_COST_MAP"),
            }
        )


def _version(package: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(package)
    except Exception:
        return None


if __name__ == "__main__":
    install()
    from rasa.__main__ import main

    sys.argv = ["rasa", *sys.argv[1:]]
    main()
