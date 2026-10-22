"""Quote the validated factory tool result instead of a model-authored verdict.
sow: software-factories-masterclass-SOW-02
"""
import json
import math
import re
from rasa.mantle.hooks import (
    IncomingMessagePayload, ModelResponsePayload, ToolResultPayload,
    modify_model_response, modify_tool_result, on_incoming_message,
)
from scripted import gate_record

_pending = {}
_UNAVAILABLE = 'Factory tool result: NOT_READY. No validated verdict was returned; no acceptance or deployment is established.'


@on_incoming_message()
async def clear_previous_turn(message: IncomingMessagePayload) -> None:
    _pending.pop(message.sender_id, None)


def quote_result(value):
    record = gate_record(value)
    if not record:
        return _UNAVAILABLE
    verdict = record.get('verdict')
    if record.get('mode') not in ('LIVE', 'SCRIPTED'):
        return _UNAVAILABLE
    calls, seconds = record.get('builder_calls'), record.get('seconds')
    if type(calls) is not int or calls < 0 or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        return _UNAVAILABLE
    if verdict in ('ACCEPT', 'REJECT') and not re.fullmatch(r'[0-9a-f]{64}', str(record.get('fingerprint', ''))):
        return _UNAVAILABLE
    failing = record.get('failing_test')
    if verdict == 'ACCEPT' and failing is not None:
        return _UNAVAILABLE
    if verdict == 'REJECT' and not re.fullmatch(r'test_[A-Za-z0-9_]{1,160}', str(failing)):
        return _UNAVAILABLE
    keys = ('verdict', 'failing_test', 'fingerprint', 'builder_calls', 'seconds', 'mode')
    quoted = {key: record.get(key) for key in keys}
    return 'Factory tool result (authoritative):\n' + json.dumps(quoted, indent=2, sort_keys=True) + '\nNothing was deployed.'


@modify_tool_result()
async def remember_factory_result(result: ToolResultPayload) -> ToolResultPayload:
    if result.tool_name in ('run_factory', 'mcp/factory:run_factory'):
        _pending[result.sender_id] = _UNAVAILABLE if result.is_error else quote_result(result.value)
    return result


@modify_model_response()
async def buffered_scripted_reply(response: ModelResponsePayload) -> ModelResponsePayload:
    # The modifier also requests non-streaming, so unchecked model text is never
    # streamed before the authoritative tool quote replaces the final response.
    if response.tool_calls and not response.text:
        return response
    quoted = _pending.get(response.sender_id)
    if quoted is None:
        return response
    if not response.tool_calls:
        _pending.pop(response.sender_id, None)
    return response.model_copy(update={'text': quoted})
