"""Verdict card: built by code from the gate record and sent straight to the dialogue."""
import re

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

MARK = {'ACCEPT': '🟢', 'REJECT': '🔴', 'NOT_READY': '🟡'}
HEADLINE = {
    'ACCEPT': 'ACCEPT: the locked tests passed',
    'REJECT': 'REJECT: a locked test failed',
    'NOT_READY': 'NOT_READY: no verdict was obtained',
}
BAR = {'ACCEPT': '▰▰▰▰▰▰▰▰▰▰', 'REJECT': '▰▰▰▰▰▱▱▱▱▱', 'NOT_READY': '▱▱▱▱▱▱▱▱▱▱'}


def card_text(request, verdict, failing_test, fingerprint, mode, builder_calls, seconds, reason):
    verdict = verdict if verdict in MARK else 'NOT_READY'
    lines = [
        f'{MARK[verdict]}  {HEADLINE[verdict]}',
        '━━━━━━━━━━━━━━',
        f'Request   {request}',
    ]
    if mode == 'LIVE':
        lines.append(f'Builder   LIVE, gpt-6-astra · {builder_calls} tool calls · {seconds} s')
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


@tool(description='Show the verdict card for a finished factory check. Call once, right after run_factory returns, with its values.')
async def show_verdict_card(request: str, verdict: str, failing_test: str = '', fingerprint: str = '',
                            mode: str = 'SCRIPTED', builder_calls: int = 0, seconds: float = 0.0,
                            reason: str = '', context: ToolContext = None) -> ToolResult:
    await context.send(card_text(request, verdict, failing_test, fingerprint, mode, builder_calls, seconds, reason))
    return ToolResult(llm_response={'card': 'shown'})


def card_svg(request, verdict, failing_test, fingerprint, mode, builder_calls, seconds, reason=''):
    from html import escape
    verdict = verdict if verdict in MARK else 'NOT_READY'
    colour = {'ACCEPT': '#1f9d55', 'REJECT': '#d64545', 'NOT_READY': '#d49a00'}[verdict]
    passed = {'ACCEPT': 10, 'REJECT': 5, 'NOT_READY': 0}[verdict]
    cells = ''.join(f'<rect x="{24 + i * 30}" y="132" width="24" height="12" rx="3" fill="{colour if i < passed else "#d9dee7"}"/>' for i in range(10))
    builder = f'LIVE · gpt-6-astra · {builder_calls} tool calls · {seconds} s' if mode == 'LIVE' else 'SCRIPTED · supplied attempt · 0 model calls'
    detail = f'Failed: {failing_test}' if verdict == 'REJECT' else f'Attempt {fingerprint[:12]}…' if fingerprint else (reason or 'No verdict was obtained.')
    def wrap(value, width):
        out, line = [], ''
        for part in re.findall(r'[^_ ]*[_ ]|[^_ ]+$', value):
            if len(line) + len(part) > width and line:
                out.append(line)
                line = ''
            line += part
        return (out + [line])[:3]
    rows = [('Request', wrap(request, 34)), ('Builder', wrap(builder, 34)), ('Result', wrap(detail, 34))]
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


@tool(description='Show the verdict as a picture card for a finished factory check. Call once, right after run_factory returns, with its values.')
async def show_verdict_image(request: str, verdict: str, failing_test: str = '', fingerprint: str = '',
                             mode: str = 'SCRIPTED', builder_calls: int = 0, seconds: float = 0.0,
                             reason: str = '', context: ToolContext = None) -> ToolResult:
    from urllib.parse import quote
    from rasa.mantle.orchestration.turn_context import current_turn_context
    from rasa.shared.core.events import BotUttered
    turn = current_turn_context()
    uri = 'data:image/svg+xml;utf8,' + quote(card_svg(request, verdict, failing_test, fingerprint, mode, builder_calls, seconds, reason))
    turn.tracker_handle.apply_events([BotUttered(text='', data={'image': uri}, metadata={'mantle_response_source': 'tool'})])
    await turn.output_channel.send_response(turn.sender_id, {'text': '', 'image': uri})
    return ToolResult(llm_response={'card': 'shown'})
