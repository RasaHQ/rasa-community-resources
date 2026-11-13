"""Verdict card: built by code from the gate record and sent straight to the dialogue.

The card tools take no verdict values. They read the result that run_factory
itself returned in this turn, as recorded on the tracker, so a model cannot put
a verdict, a test name or a count on the card that the gate did not produce.
"""
import json
import re

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

VERDICTS = ('ACCEPT', 'REJECT', 'NOT_READY')

MARK = {'ACCEPT': '🟢', 'REJECT': '🔴', 'NOT_READY': '🟡'}
HEADLINE = {
    'ACCEPT': 'ACCEPT: the locked tests passed',
    'REJECT': 'REJECT: a locked test failed',
    'NOT_READY': 'NOT_READY: no verdict was obtained',
}
BAR = {'ACCEPT': '▰▰▰▰▰▰▰▰▰▰', 'REJECT': '▰▰▰▰▰▱▱▱▱▱', 'NOT_READY': '▱▱▱▱▱▱▱▱▱▱'}


def _record(value):
    """The gate record inside a tool result, or None."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, dict):
        if value.get('verdict') in VERDICTS:
            return value
        for key in ('structuredContent', 'content', 'text', 'value', 'result'):
            found = _record(value.get(key))
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _record(item)
            if found:
                return found
    return None


def _number(value, kind, default):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return kind(value)


def last_gate(events):
    """(request, record) from the latest successful run_factory call in this turn.

    Only events after the caller's latest message count, so an earlier turn's
    verdict is never shown again. Returns None when there is none."""
    latest = max((i for i, event in enumerate(events) if type(event).__name__ == 'UserUttered'), default=-1)
    for event in reversed(events[latest + 1:]):
        if type(event).__name__ not in ('McpToolExecuted', 'ToolExecuted'):
            continue
        if not str(getattr(event, 'tool_name', '')).endswith('run_factory') or getattr(event, 'is_error', False):
            continue
        record = _record(getattr(event, 'result', None))
        if record is None:
            continue
        arguments = getattr(event, 'arguments', None) or getattr(event, 'tool_args', None) or {}
        request = arguments.get('request') if isinstance(arguments, dict) else None
        return str(request or 'unknown'), {
            'verdict': record['verdict'],
            'failing_test': str(record.get('failing_test') or ''),
            'fingerprint': str(record.get('fingerprint') or ''),
            'mode': 'LIVE' if record.get('mode') == 'LIVE' else 'SCRIPTED',
            'builder_model': str(record.get('builder_model') or ''),
            'builder_calls': _number(record.get('builder_calls'), int, 0),
            'seconds': _number(record.get('seconds'), float, 0.0),
            'reason': str(record.get('reason') or ''),
        }
    return None


NO_GATE = {'card': 'not_shown', 'reason': 'no run_factory result in this turn'}


def card_text(request, verdict, failing_test, fingerprint, mode, builder_calls, seconds, reason, builder_model=''):
    verdict = verdict if verdict in MARK else 'NOT_READY'
    lines = [
        f'{MARK[verdict]}  {HEADLINE[verdict]}',
        '━━━━━━━━━━━━━━',
        f'Request   {request}',
    ]
    if mode == 'LIVE':
        lines.append(f'Builder   LIVE{", " + builder_model if builder_model else ""} · {builder_calls} tool calls · {seconds} s')
    else:
        lines.append('Builder   SCRIPTED · supplied attempt · 0 model calls')
    lines.append(f'Gate      {BAR[verdict]}')
    if verdict == 'REJECT':
        lines.append(f'Failed    {failing_test or "unknown"}')
    if verdict == 'NOT_READY' and reason:
        lines.append(f'Reason    {reason}')
    if fingerprint:
        lines.append(f'Attempt   {fingerprint[:12]}…')
    lines.append('Status    judged only · nothing released or deployed')
    return '\n'.join(lines)


@tool(description='Show the verdict card for the factory check just run in this turn. Takes no values: '
                   'the card is built from run_factory\'s own result.')
async def show_verdict_card(context: ToolContext = None) -> ToolResult:
    found = last_gate(context.events)
    if found is None:
        return ToolResult(llm_response=NO_GATE)
    request, gate = found
    await context.send(card_text(request, **gate))
    return ToolResult(llm_response={'card': 'shown', 'verdict': gate['verdict']})


def card_svg(request, verdict, failing_test, fingerprint, mode, builder_calls, seconds, reason='', builder_model=''):
    from html import escape
    verdict = verdict if verdict in MARK else 'NOT_READY'
    colour = {'ACCEPT': '#1f9d55', 'REJECT': '#d64545', 'NOT_READY': '#d49a00'}[verdict]
    passed = {'ACCEPT': 10, 'REJECT': 5, 'NOT_READY': 0}[verdict]
    cells = ''.join(f'<rect x="{24 + i * 30}" y="132" width="24" height="12" rx="3" fill="{colour if i < passed else "#d9dee7"}"/>' for i in range(10))
    model = f' · {builder_model}' if builder_model else ''
    builder = f'LIVE{model} · {builder_calls} tool calls · {seconds} s' if mode == 'LIVE' else 'SCRIPTED · supplied attempt · 0 model calls'
    if verdict == 'REJECT':
        detail = f'Failed: {failing_test or "unknown"}'
    elif verdict == 'NOT_READY':
        detail = reason or 'No verdict was obtained.'  # why no verdict, before anything else
    else:
        detail = f'Attempt {fingerprint[:12]}…' if fingerprint else 'Attempt fingerprint unavailable.'
    def wrap(value, width):
        out, line = [], ''
        for part in re.findall(r'[^_ ]*[_ ]|[^_ ]+$', value):
            if len(line) + len(part) > width and line:
                out.append(line)
                line = ''
            line += part
        return (out + [line])[:3]
    rows = [('Request', wrap(request, 34)), ('Builder', wrap(builder, 34)), ('Result', wrap(detail, 34))]
    if verdict != 'ACCEPT' and fingerprint:
        rows.append(('Attempt', [f'{fingerprint[:12]}…']))
    text, y = '', 176
    for label, lines in rows:
        text += f'<text x="24" y="{y}" font-size="12" fill="#5b6472">{escape(label)}</text>'
        for line in lines:
            text += f'<text x="92" y="{y}" font-size="12" fill="#1c2430">{escape(line)}</text>'
            y += 16
        y += 6
    height = y + 34
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="360" height="{height}" viewBox="0 0 360 {height}" font-family="Helvetica,Arial,sans-serif">'
            f'<rect width="360" height="{height}" rx="14" fill="#ffffff" stroke="#d9dee7"/><rect width="360" height="64" rx="14" fill="{colour}"/>'
            f'<rect y="40" width="360" height="24" fill="{colour}"/>'
            f'<text x="24" y="40" font-size="20" font-weight="700" fill="#fff">{verdict.replace("_", " ")}</text>'
            f'<text x="24" y="92" font-size="12" fill="#5b6472">LOCKED TESTS</text>'
            f'<text x="24" y="116" font-size="16" font-weight="600" fill="#1c2430">{HEADLINE[verdict].split(": ")[1]}</text>'
            f'{cells}{text}'
            f'<text x="24" y="{height - 14}" font-size="11" fill="#8a93a1">Judged only · nothing released or deployed</text></svg>')


@tool(description='Show the verdict as a picture card for the factory check just run in this turn. '
                   'Takes no values: the card is built from run_factory\'s own result.')
async def show_verdict_image(context: ToolContext = None) -> ToolResult:
    from urllib.parse import quote
    from rasa.mantle.orchestration.turn_context import current_turn_context
    from rasa.shared.core.events import BotUttered
    found = last_gate(context.events)
    if found is None:
        return ToolResult(llm_response=NO_GATE)
    request, gate = found
    turn = current_turn_context()
    if turn.is_cancelled:  # the caller interrupted: record and send nothing
        return ToolResult(llm_response={'card': 'not_shown', 'reason': 'interrupted'})
    uri = 'data:image/svg+xml;utf8,' + quote(card_svg(request, **gate))
    turn.tracker_handle.apply_events([BotUttered(text='', data={'image': uri}, metadata={'mantle_response_source': 'tool'})])
    await turn.output_channel.send_response(turn.sender_id, {'text': '', 'image': uri})
    return ToolResult(llm_response={'card': 'shown', 'verdict': gate['verdict']})
