"""Recorded sources for the normal Mantle/MCP workflow; no alternate renderer.
sow: software-factories-masterclass-SOW-02
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
EXPECTED = {'flight_status', 'weather_hourly', 'arrival_timeline', 'market_watchlist'}


def load_recording(path=ROOT / 'recorded-journey.json'):
    from zeo_core.contracts.ui.widgets import CardState
    raw = Path(path).read_bytes()
    if len(raw) > 262144:
        raise ValueError('recording_too_large')
    record = json.loads(raw)
    if record['schema'] != 'recorded-classroom-cards-v1' or len(record['cards']) != 4:
        raise ValueError('invalid_recording')
    cards = []
    for value in record['cards']:
        state = CardState.model_validate(value)
        if state.replaced or state.data_ref.error is not None:
            raise ValueError('incomplete_recording')
        reference = state.data_ref.model_copy(update={'replay': True}).check(state.component)
        cards.append(state.model_copy(update={'data_ref': reference}))
    if {card.component for card in cards} != EXPECTED:
        raise ValueError('missing_recorded_component')
    return record, cards


def make_runner():
    sys.path.insert(0, str(ROOT / 'demo'))
    from briefing.airports import airport
    from briefing.data import timeline_payload
    from briefing.jobs import BriefingRefused
    from briefing.public_sources import PublicSourcesRunner
    from zeo_core.contracts.ui.widgets import Assumption, TRANSFER_LABEL
    record, states = load_recording()
    references = {state.component: state.data_ref for state in states}
    flight = references['flight_status'].payload
    destination = airport(record['place']['code'])

    class RecordedSources:
        def read_briefing(self, callsign, *, transfer_minutes, meeting_time, currencies, stated_destination=None):
            if (callsign != flight['flight_number'] or stated_destination is None
                    or stated_destination.code != destination['ident'] or tuple(currencies) != ('USD', 'GBP')):
                raise BriefingRefused('outside_recorded_journey')
            # Recompute only the planning result, using the canonical helper.
            # Aircraft, weather and currency observations keep their recorded values.
            payload = timeline_payload(arrival=flight['estimated_arrival'],
                meeting_time=meeting_time.isoformat(), transfer_minutes=transfer_minutes)
            # The renderer already shows meeting_time separately. Keep two
            # journey steps and round the computed margin for the traveller.
            payload['steps'] = payload['steps'][:2]
            payload['steps'][0]['label'] = 'Computed landing from recorded position'
            payload['margin_minutes'] = round(payload['margin_minutes'])
            timeline = references['arrival_timeline'].model_copy(update={
                'id': 'recorded-timeline-' + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24],
                'payload': payload, 'source': 'Computed from recorded position, stated transfer and meeting',
                'assumptions': [Assumption(label=TRANSFER_LABEL, value=transfer_minutes, kind='assumption')],
                'replay': True}).check('arrival_timeline')
            return {**references, 'arrival_timeline': timeline}

        def close(self):
            pass  # No HTTP or model client exists in this source adapter.

    class RecordedRunner(PublicSourcesRunner):
        def find_flights(self, destination):
            return {'status': 'needs_input', 'needs_input': {'field': 'flight',
                'question': 'This replay contains United 1162 to Newark. Tell me that flight number to use the recorded journey.'}}

    # Relative words refer to the recording's day, never the reader's current day.
    clock = datetime.fromisoformat(record['recorded_at'])
    return RecordedRunner(RecordedSources(), clock=lambda: clock)
