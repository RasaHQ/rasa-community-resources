"""Managed Agents callbacks read real public sources; prose never makes a card."""
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from datetime import datetime
import json

from briefing.native_runtime import native_turn
from briefing.public_sources import PublicSourcesRunner
from zeo_core.integrations.briefing_sources.flight import flight
from zeo_core.integrations.briefing_sources.timeline import unavailable


class LivePublicSourcesRunner(PublicSourcesRunner):
    def __init__(self, client_factory, *, model, sources=None, invoke=None, clock=None):
        super().__init__(sources, clock=clock)
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError('live_model_required')
        self.client_factory, self.model, self.invoke = client_factory, model, invoke

    def _source_reader(self, inputs):
        # The model selects the tools. Dependencies share one validated flight
        # observation, but a market-only selection never contacts ADSB or MET.
        cache = {}
        flight_lock = RLock()
        def observed():
            with flight_lock:
                return observed_once()
        def observed_once():
            if 'flight' not in cache:
                destination = {}
                if inputs.get('destination'):
                    from briefing.airports import stated_destination
                    destination['stated_destination'] = stated_destination(inputs['destination'])
                cache['flight'] = flight(self.sources.http, inputs['callsign'],
                                        fetched_at=self._clock(), **destination)
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
                                      self._clock(), 'route_not_provided' if result.reference.error is None
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
        # One model-selected tool starts a coherent four-card read. Independent
        # callbacks run concurrently; weather/timeline share one fresh flight.
        # No callback means no source request and no fabricated cards.
        from zeo_core.integrations.agents import function_tool
        tool_name = 'read_briefing'
        def read_all(arguments):
            with ThreadPoolExecutor(max_workers=4, thread_name_prefix='briefing-source') as pool:
                pending = {name: pool.submit(handler, arguments)
                           for name, handler in handlers.items()}
                return {name: future.result() for name, future in pending.items()}
        aggregate_tool = function_tool(tool_name,
            'Read the flight, weather, rate and computed timeline for this journey',
            tools[0]['parameters'])
        # A fresh native session for every revision; no legacy session reuse.
        with self.client_factory() as client:
            return native_turn(client, agent={'model': self.model, 'tools': [aggregate_tool],
                'instructions': 'Call read_briefing once to build all four cards. '
                                'It reads independent public sources concurrently and returns '
                                'validated observations or honest unavailable results. '
                                'Never invent values or retry unavailable sources. '
                                'Finish with a short completion message after the tool.'},
                text=json.dumps({'request': work.text, 'journey': work.inputs or {}},
                                allow_nan=False, separators=(',', ':')),
                handlers={tool_name: read_all}, invoke=self.invoke, max_calls=1)
