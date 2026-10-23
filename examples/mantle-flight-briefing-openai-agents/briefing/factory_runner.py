"""Opt-in three-card baseline and reviewed market-card receiving seam.

sow: software-factories-masterclass-SOW-02
Normal PublicSourcesRunner remains the existing four-card product. This runner
uses the same journey parser, Core references, tool control, Jobs and HTTP app.
"""
from datetime import datetime

from zeo_core.contracts.ui.widgets import Assumption
from zeo_core.integrations.agents import function_tool
from zeo_core.integrations.briefing_sources.flight import flight as read_flight
from zeo_core.integrations.briefing_sources.timeline import unavailable

from briefing.factory_receiver import load_accepted_market
from briefing.jobs import Answer, BriefingRefused
from briefing.public_sources import PublicSourcesRunner

BASE_COMPONENTS = ('flight_status', 'weather_hourly', 'arrival_timeline')


class FactoryRunner(PublicSourcesRunner):
    def __init__(self, sources=None, *, clock=None, received_directory=None):
        # Refuse altered staging evidence before allocating a source client.
        self.received_directory = received_directory
        self.market_card = None if received_directory is None else load_accepted_market(received_directory)
        super().__init__(sources, clock=clock)

    async def __call__(self, work):
        if work.text.strip().startswith('Replay ') or (work.inputs or {}).get('source_mode') == 'replay':
            raise BriefingRefused('factory_public_sources_required')
        return await super().__call__(work)

    def _references(self, inputs):
        from briefing.airports import stated_destination
        destination = {} if not inputs.get('destination') else {
            'stated_destination': stated_destination(inputs['destination'])}
        now = self._clock()
        observed = read_flight(self.sources.http, inputs['callsign'], fetched_at=now, **destination)
        flight = observed.reference
        if (observed.destination_latitude is not None and observed.destination_longitude is not None
                and observed.destination is not None):
            estimate = flight.payload.get('estimated_arrival')
            weather = self.sources.weather(observed.destination_latitude, observed.destination_longitude,
                location=observed.destination, arrival=datetime.fromisoformat(estimate) if isinstance(estimate, str) else None)
        else:
            weather = unavailable('weather_hourly', 'MET Norway (api.met.no), CC BY 4.0', now,
                                  'route_not_provided' if flight.error is None else 'destination_unavailable')
        references = {'flight_status': flight, 'weather_hourly': weather,
            'arrival_timeline': self.sources.arrival_timeline(flight,
                transfer_minutes=inputs['transfer_minutes'], meeting_time=datetime.fromisoformat(inputs['meeting_time']))}
        if self.market_card is not None:
            references['market_watchlist'] = self.market_card(self.sources, ('USD', 'GBP'))
        return references

    def _read(self, work, inputs):
        if self.received_directory is not None:
            self.market_card = load_accepted_market(self.received_directory)
        references = self._references(inputs)
        cards = {}

        def handler(component):
            def supply(arguments):
                if set(arguments) - {'destination'} or (
                        arguments and arguments.get('destination') != inputs.get('destination')):
                    raise ValueError('unexpected_source_arguments')
                reference = references[component].check(component)
                if component == 'arrival_timeline' and inputs.get('transfer_assumed') and reference.error is None:
                    reference = reference.model_copy(update={'assumptions': [*reference.assumptions,
                        Assumption(label='airport_city_planning_allowance',
                            value='Bundled planning assumption; changeable, not live traffic or a guaranteed airport exit time.',
                            kind='assumption')]}).check(component)
                cards[component] = reference
                return {'data_ref': reference.model_dump(mode='json')}
            return supply

        components = BASE_COMPONENTS + (() if self.market_card is None else ('market_watchlist',))
        handlers = {'read_' + component: handler(component) for component in components}
        tools = [function_tool(name, 'Read a validated public source reference', {
            'type': 'object', 'properties': {}, 'additionalProperties': False}) for name in handlers]
        turn = self._invoke(work, tools, handlers)
        return Answer(turn, cards, required_components=components, inputs=inputs)
