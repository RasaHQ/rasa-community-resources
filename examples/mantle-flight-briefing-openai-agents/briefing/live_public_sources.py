"""Managed Agents callbacks read real public sources; prose never makes a card."""
from datetime import datetime, timezone
import json

from briefing.native_runtime import native_turn
from briefing.public_sources import PublicSourcesRunner
from zeo_core.integrations.briefing_sources.flight import flight
from zeo_core.integrations.briefing_sources.timeline import unavailable


class LivePublicSourcesRunner(PublicSourcesRunner):
    def __init__(self, client_factory, *, model, sources=None, invoke=None):
        super().__init__(sources)
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError('live_model_required')
        self.client_factory, self.model, self.invoke = client_factory, model, invoke

    def _source_reader(self, inputs):
        # The model selects the tools. Dependencies share one validated flight
        # observation, but a market-only selection never contacts ADSB or MET.
        cache = {}
        def observed():
            if 'flight' not in cache:
                destination = {}
                if inputs.get('destination'):
                    from briefing.airports import stated_destination
                    destination['stated_destination'] = stated_destination(inputs['destination'])
                cache['flight'] = flight(self.sources.http, inputs['callsign'],
                                        fetched_at=datetime.now(timezone.utc), **destination)
            return cache['flight']
        def read(component):
            if component in cache:
                return cache[component]
            if component == 'market_watchlist':
                ref = self.sources.market(('USD', 'GBP'))
            elif component == 'flight_status':
                ref = observed().reference
            elif component == 'arrival_timeline':
                ref = self.sources.arrival_timeline(observed().reference,
                    transfer_minutes=inputs['transfer_minutes'],
                    meeting_time=datetime.fromisoformat(inputs['meeting_time']))
            else:
                result = observed()
                if result.destination is None:
                    ref = unavailable('weather_hourly', 'MET Norway (api.met.no), CC BY 4.0',
                                      datetime.now(timezone.utc), 'route_not_provided' if result.reference.error is None
                                      else 'destination_unavailable')
                else:
                    estimate = result.reference.payload.get('estimated_arrival')
                    ref = self.sources.weather(result.destination_latitude,
                        result.destination_longitude, location=result.destination,
                        arrival=datetime.fromisoformat(estimate) if isinstance(estimate, str) else None)
            cache[component] = ref
            return ref
        return read

    def _invoke(self, work, tools, handlers):
        # A fresh native session for every revision; no legacy session reuse.
        with self.client_factory() as client:
            return native_turn(client, agent={'model': self.model, 'tools': tools,
                'instructions': 'Read each offered public source tool once to build all four cards. '
                                'Tools return validated observations or honest unavailable results. '
                                'Never invent values or retry unavailable sources. '
                                'Finish with a short completion message after the tools.'},
                text=json.dumps({'request': work.text, 'journey': work.inputs or {}},
                                allow_nan=False, separators=(',', ':')),
                handlers=handlers, invoke=self.invoke, max_calls=8)
