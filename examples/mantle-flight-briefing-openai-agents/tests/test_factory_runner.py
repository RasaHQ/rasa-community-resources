"""Offline Core/Jobs/HTTP proof; no provider call, process restart or live acceptance.
sow: software-factories-masterclass-SOW-02
"""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.factory_receiver import ReceiverRefused
from briefing.factory_runner import FactoryRunner, BASE_COMPONENTS
from briefing.jobs import BriefingRefused, Jobs, Owner, Work
from briefing.mcp_app import create_app
from briefing.public_sources import PublicSourcesRunner
from zeo_core.integrations.briefing_sources import PublicBriefingSources, PublicSourceHTTP
from test_factory_receiver import stage_fixture

NOW = datetime(2026, 10, 22, 1, tzinfo=timezone.utc)
REQUEST = 'callsign=TEST123 destination=EDDF meeting=2026-10-22T06:00:00Z transfer=45'


def fixture_sources(*, unavailable_market=False):
    requests = []
    tick = [0.0]

    def handler(request):
        requests.append(request.url.host)
        if request.url.host == 'api.adsb.lol':
            if request.method == 'GET':
                return httpx.Response(200, json={'now': NOW.timestamp() * 1000, 'ac': [{
                    'flight': 'TEST123', 'lat': 50.0, 'lon': 0.0, 'gs': 400.0,
                    'seen_pos': 5, 'alt_baro': 30000}]})
            return httpx.Response(200, json=[{'callsign': 'TEST123', 'plausible': True,
                '_airports': [{'icao': 'KJFK', 'lat': 40.6, 'lon': -73.7},
                              {'icao': 'EGLL', 'lat': 51.4775, 'lon': -0.4614}]}])
        if request.url.host == 'api.met.no':
            return httpx.Response(200, json={'properties': {'meta': {'updated_at': NOW.isoformat()},
                'timeseries': [{'time': (NOW + timedelta(hours=i)).isoformat(), 'data': {
                    'instant': {'details': {'air_temperature': 15 + i}},
                    'next_1_hours': {'details': {'precipitation_amount': .1,
                                                 'probability_of_precipitation': 25}}}}
                               for i in range(4)]}})
        if request.url.host != 'data-api.ecb.europa.eu':
            raise AssertionError('Unexpected fixture source')
        if unavailable_market:
            return httpx.Response(503)
        return httpx.Response(200, text='FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n'
            'D,USD,EUR,SP00,A,2026-10-20,1.1\nD,USD,EUR,SP00,A,2026-10-21,1.2\n'
            'D,GBP,EUR,SP00,A,2026-10-20,0.8\nD,GBP,EUR,SP00,A,2026-10-21,0.9\n')

    def sleep(seconds):
        tick[0] += seconds
    sources = PublicBriefingSources(PublicSourceHTTP(transport=httpx.MockTransport(handler),
        clock=lambda: NOW, monotonic=lambda: tick[0], sleep=sleep), clock=lambda: NOW)
    return sources, requests


async def completed(jobs, *, expected_status='complete'):
    owner = Owner('mantle', 'offline-f7-control')
    started = await jobs.briefing(owner, action='start', request=REQUEST)
    for _ in range(200):
        state = await jobs.briefing(owner, action='get', job_id=started['job_id'])
        if state['status'] not in ('started', 'running'):
            break
        await asyncio.sleep(.01)
    if state['status'] != expected_status:
        raise AssertionError(state)
    return state


async def board_control(receiving_directory=None, *, unavailable_market=False):
    sources, requests = fixture_sources(unavailable_market=unavailable_market)
    runner = FactoryRunner(sources, clock=lambda: NOW, received_directory=receiving_directory)
    jobs = Jobs(runner, replacement_plan=runner.replacement_plan, ownership_mode='capability')
    try:
        state = await completed(jobs, expected_status='incomplete' if unavailable_market else 'complete')
        app = create_app(jobs, transport_token='synthetic-offline-f7-transport-token')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1:8942') as client:
            page = await client.get('/cards')
            combined = await client.get('/')
        if page.status_code != 200 or combined.status_code != 200:
            raise AssertionError('Real HTTP app did not serve the offline control')
        return state, page.text, combined.text, requests
    finally:
        await jobs.close()
        runner.close()


class FactoryRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_http_transitions_three_to_four_preserving_cards_and_meeting(self):
        with tempfile.TemporaryDirectory() as directory:
            _, received, _ = stage_fixture(Path(directory))
            before, before_html, _, before_requests = await board_control()
            after, after_html, combined, after_requests = await board_control(received)
        self.assertEqual(len(before['cards']), 3)
        self.assertEqual(len(after['cards']), 4)
        self.assertNotIn('data-api.ecb.europa.eu', before_requests)
        self.assertIn('data-api.ecb.europa.eu', after_requests)
        first = {c['event']['component']: c['data_ref'] for c in before['cards']}
        second = {c['event']['component']: c['data_ref'] for c in after['cards']}
        self.assertEqual(set(first), set(BASE_COMPONENTS))
        self.assertEqual(set(second), {*BASE_COMPONENTS, 'market_watchlist'})
        for component in BASE_COMPONENTS:
            # New job references have fresh IDs; values/provenance must agree.
            self.assertEqual({k: v for k, v in first[component].items() if k != 'id'},
                             {k: v for k, v in second[component].items() if k != 'id'})
        self.assertEqual(first['arrival_timeline']['payload']['meeting_time'],
                         second['arrival_timeline']['payload']['meeting_time'])
        self.assertNotIn('Market watchlist', before_html)
        for text in ('Market watchlist', 'daily reference rate', '2026-10-21',
                     'PROVIDER DATA', 'COMPUTED from two reference days'):
            self.assertIn(text, after_html)
        self.assertIn('Mantle conversation', combined)
        self.assertFalse(second['market_watchlist']['replay'])
        self.assertNotIn('synthetic-offline-f7-transport-token', after_html)

    async def test_market_failure_keeps_the_unavailable_reference_and_other_cards(self):
        with tempfile.TemporaryDirectory() as directory:
            _, received, _ = stage_fixture(Path(directory))
            state, page, _, _ = await board_control(received, unavailable_market=True)
        market = next(c['data_ref'] for c in state['cards'] if c['event']['component'] == 'market_watchlist')
        self.assertEqual(state['status'], 'incomplete')
        self.assertIsNotNone(market['error'])
        self.assertFalse(market['payload'])
        self.assertEqual(len(state['cards']), 4)
        self.assertIn('unavailable', page.lower())

    async def test_revalidates_staged_bytes_before_each_source_read(self):
        with tempfile.TemporaryDirectory() as directory:
            _, received, _ = stage_fixture(Path(directory))
            sources, requests = fixture_sources()
            runner = FactoryRunner(sources, clock=lambda: NOW, received_directory=received)
            try:
                (received / 'candidate/product/briefing/market_card.py').write_text('raise AssertionError("unreviewed")')
                with self.assertRaises(ReceiverRefused):
                    await runner(Work(REQUEST, 'r', 1, None))
                self.assertEqual(requests, [])
            finally:
                runner.close()

    async def test_replay_cannot_manufacture_factory_acceptance(self):
        sources, requests = fixture_sources()
        runner = FactoryRunner(sources, clock=lambda: NOW)
        try:
            with self.assertRaises(BriefingRefused):
                await runner(Work('Replay DEMO101 missing inputs', 'r', 1, None))
            self.assertEqual(requests, [])
        finally:
            runner.close()

    async def test_normal_public_mode_still_has_four_components(self):
        sources, _ = fixture_sources()
        runner = PublicSourcesRunner(sources, clock=lambda: NOW)
        try:
            answer = await runner(Work(REQUEST, 'r', 1, None))
            self.assertEqual(set(answer.cards), {*BASE_COMPONENTS, 'market_watchlist'})
        finally:
            runner.close()


class FactoryCLIControls(unittest.TestCase):
    def test_opt_in_modes_ignore_ambient_model_credentials_and_close_on_failure(self):
        cli = importlib.import_module('briefing.__main__')
        for flag, received in [('--factory-baseline', None), ('--factory-received', 'owner-evidence')]:
            runner = Mock()
            argv = ['briefing', flag] + ([] if received is None else [received])
            with patch.object(sys, 'argv', argv), patch.dict(os.environ, {
                    'BRIEFING_MCP_TOKEN': 'synthetic-offline-cli-token-123456789',
                    'OPENAI_API_KEY': 'synthetic-ambient-key-must-not-be-used',
                    'BRIEFING_AGENTS_MODEL': 'must-not-start-a-model'}), \
                    patch('briefing.factory_runner.FactoryRunner', return_value=runner) as construct, \
                    patch.object(cli, 'create_app', side_effect=RuntimeError('offline-stop')):
                with self.assertRaisesRegex(RuntimeError, 'offline-stop'):
                    cli.main()
            construct.assert_called_once_with(received_directory=received)
            runner.close.assert_called_once()

    def test_factory_modes_are_mutually_exclusive_with_normal_modes(self):
        cli = importlib.import_module('briefing.__main__')
        for mode in ('--public-sources', '--live-model', '--factory-baseline'):
            with patch.object(sys, 'argv', ['briefing', '--factory-received', 'evidence', mode]):
                with self.assertRaises(SystemExit):
                    cli.main()


if __name__ == '__main__':
    unittest.main()
