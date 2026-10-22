"""Scripted tool control over real keyless sources; no model prose is source data.

The classroom runner takes an explicit structured journey request. The outer
Mantle conversation may collect it naturally; this parser never guesses a flight,
meeting time or transfer duration. Source clients persist for this service run,
so revisions do not reset their finite request budget or cache.
"""
import asyncio
from datetime import datetime
from dataclasses import replace
import re

from zeo_core.integrations.agents import ScriptedTransport, function_tool, run
from briefing.jobs import Answer, BriefingRefused, NeedsInput, Work
from briefing.replay import ReplayRunner


class PublicSourcesRunner:
    def __init__(self, sources=None):
        if sources is None:
            from zeo_core.integrations.briefing_sources import PublicBriefingSources
            sources = PublicBriefingSources()
        self.sources = sources
        self.replay = ReplayRunner()

    @staticmethod
    def replacement_plan(change):
        return None  # The four source references are refreshed coherently.

    async def __call__(self, work: Work) -> Answer:
        inputs = dict(work.inputs or {})
        text = work.text.strip()
        if text.startswith('Replay DEMO101') or (inputs.get('source_mode') == 'replay' and 'callsign=' not in text):
            try:
                answer = await self.replay(work)
            except NeedsInput as missing:
                raise NeedsInput(missing.field, missing.question,
                                 {**missing.inputs, 'source_mode': 'replay'}) from None
            return replace(answer, inputs={**(answer.inputs or {}), 'source_mode': 'replay'})
        inputs.pop('source_mode', None)
        callsign = re.search(r'\bcallsign=([A-Z0-9]{2,10})\b', text)
        if callsign:
            inputs['callsign'] = callsign.group(1)
        if not inputs.get('callsign'):
            raise BriefingRefused('explicit_callsign_required')
        meeting = re.search(r'\bmeeting=([^\s]+)', text)
        transfer = re.search(r'\btransfer=([0-9]{1,4})\b', text)
        awaiting = inputs.get('awaiting')
        if meeting or awaiting == 'meeting_time':
            try:
                parsed = datetime.fromisoformat(meeting.group(1) if meeting else text)
                if parsed.tzinfo is None:
                    raise ValueError
                inputs['meeting_time'] = parsed.isoformat()
            except ValueError:
                inputs.pop('meeting_time', None)
        if transfer or awaiting == 'transfer_minutes':
            match = transfer or re.fullmatch(r'([0-9]{1,4})(?: minutes?)?', text)
            if match and 0 <= int(match.group(1)) <= 1440:
                inputs['transfer_minutes'] = int(match.group(1))
            else:
                inputs.pop('transfer_minutes', None)
        inputs.pop('awaiting', None)
        for field, question in (
                ('meeting_time', 'What is the meeting time, including its date and timezone?'),
                ('transfer_minutes', 'What transfer duration in minutes should I assume?')):
            if field not in inputs:
                inputs['awaiting'] = field
                raise NeedsInput(field, question, inputs)
        return await asyncio.to_thread(self._read, work, inputs)

    def _read(self, work, inputs):
        references = self.sources.read_briefing(
            inputs['callsign'], transfer_minutes=inputs['transfer_minutes'],
            meeting_time=datetime.fromisoformat(inputs['meeting_time']),
            currencies=('USD', 'GBP'))
        cards = {}

        def handler(component):
            def supply(arguments):
                if dict(arguments):
                    raise ValueError('unexpected_source_arguments')
                reference = references[component].check(component)
                cards[component] = reference
                return {'data_ref': reference.model_dump()}
            return supply
        handlers = {'read_' + component: handler(component) for component in references}
        tools = [function_tool(name, 'Read a validated public source reference',
                 {'type': 'object', 'properties': {}, 'additionalProperties': False})
                 for name in handlers]
        turn_id = 'source-' + work.request_id
        calls = [{'type': 'function_call', 'turn_id': turn_id,
                  'call_id': 'call-' + name, 'name': name, 'arguments': {}}
                 for name in handlers]
        transport = ScriptedTransport(
            [{'type': 'agent.session.requires_action', 'required_actions': calls}],
            [{'type': 'agent.session.turn.output_text.done',
              'text': 'SCRIPTED source tool control completed. Read the validated cards, including unavailable reasons.'},
             {'type': 'agent.session.turn.completed'}],
            session_id=work.session_id or turn_id)
        turn = run(transport, agent={'tools': tools}, environment={}, text=work.text,
                   handlers=handlers, session_id=work.session_id)
        replies = [event for event in transport.sent if event['type'].endswith('tool_result')]
        if len(replies) != len(calls) or any(not event.get('success') for event in replies):
            raise ValueError('source_tool_results_incomplete')
        return Answer(turn, cards, required_components=tuple(references), inputs=inputs)

    def close(self):
        self.sources.close()
