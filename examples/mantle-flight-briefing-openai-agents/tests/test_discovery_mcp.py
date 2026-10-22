"""Actual MCP requests with injected search results; no provider or model call."""
import asyncio
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.jobs import Jobs, Owner, BriefingRefused, NeedsInput
from briefing.mcp_app import create_app
from briefing.traveller import discovery_notice, journey, TravellerQuestion


class SearchRunner:
    def __init__(self):
        self.work = []
        self.fail = False

    def find_flights(self, destination):
        if self.fail:
            raise RuntimeError('private provider diagnostic')
        return {'status': 'found', 'source_date': '2026-10-22',
                'label': 'headed to New York per published route data; position live',
                'coverage': 'Partial published route subset', 'partial': False,
                'candidates': [dict(choice=n, callsign=call, airline=airline,
                    destination='KJFK', origin='EDDF', origin_name='Frankfurt',
                    altitude_feet=25000, position_age_seconds=5,
                    landing_estimate_minutes=30) for n, call, airline in
                    [(1, 'DLH400', 'Lufthansa'), (2, 'UAL57', 'United')]]}

    async def __call__(self, work):
        self.work.append(work)
        try:
            inputs = journey(work.text, work.inputs)
        except TravellerQuestion as missing:
            raise NeedsInput(missing.field, missing.question, missing.inputs) from None
        raise AssertionError('this control must stop before any source call')


class DiscoveryMCP(unittest.IsolatedAsyncioTestCase):
    async def test_actual_tools_choose_second_then_ask_meeting_without_technical_inputs(self):
        runner = SearchRunner()
        jobs = Jobs(runner, ownership_mode='capability')
        app = create_app(jobs, transport_token='synthetic-discovery-transport-no-authority')
        async with app._app.router.lifespan_context(app._app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1:8942',
                    headers={'accept': 'application/json, text/event-stream',
                             'authorization': 'Bearer synthetic-discovery-transport-no-authority'}) as client:
                count = 0
                async def rpc(method, params):
                    nonlocal count
                    count += 1
                    response = await client.post('/mcp', json={'jsonrpc': '2.0', 'id': count, 'method': method, 'params': params})
                    self.assertEqual(response.status_code, 200)
                    return response.json()['result']
                await rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'control', 'version': '1'}})
                tools = (await rpc('tools/list', {}))['tools']
                self.assertEqual([t['name'] for t in tools], ['briefing', 'find_flights'])
                for tool in tools:
                    self.assertFalse(tool['inputSchema']['additionalProperties'])
                    self.assertFalse({'ctx', 'owner', 'session_id', 'user_id'} & set(tool['inputSchema']['properties']))
                async def call(name, args):
                    return await rpc('tools/call', {'name': name, 'arguments': args})
                search = (await call('find_flights', {'destination': 'New York'}))['structuredContent']
                self.assertEqual(len(search['candidates']), 2)
                private_id = search['discovery_id']
                page = (await client.get('/cards')).text
                self.assertIn('United Airlines 57', page)
                self.assertNotIn(private_id, page)
                for args in [{'destination': 'JFK', 'owner': 'invented'}, {'destination': 123}]:
                    self.assertTrue((await call('find_flights', args))['isError'])
                started = (await call('briefing', {'action': 'start', 'request': 'the second one',
                    'discovery_id': private_id, 'choice': 2}))['structuredContent']
                job_id = started['briefing_id']
                await jobs._jobs[job_id].task
                status = (await call('briefing', {'action': 'get', 'briefing_id': job_id}))['structuredContent']
                self.assertEqual(status['status'], 'needs_input')
                self.assertEqual(status['needs_input']['field'], 'meeting_time')
                self.assertEqual(runner.work[-1].inputs['callsign'], 'UAL57')
                self.assertNotIn('ISO', status['needs_input']['question'])
                self.assertNotIn('timezone', status['needs_input']['question'])

    async def test_discovery_capability_owner_expiry_and_failure_are_explicit(self):
        runner = SearchRunner()
        jobs = Jobs(runner)
        owner = Owner('mantle', 'one')
        try:
            result = await jobs.briefing(owner, action='find_flights', request='New York')
            key = result['discovery_id']
            for wrong_owner, selected_key, choice in [(Owner('mantle', 'two'), key, 1),
                    (owner, 'brf_wrong', 1), (owner, key, True), (owner, key, 3)]:
                with self.assertRaises(BriefingRefused):
                    await jobs.briefing(wrong_owner, action='start', request='that flight', discovery_id=selected_key, choice=choice)
            entry = jobs._discoveries[key]
            jobs._discoveries[key] = (entry[0], entry[1] - 601, entry[2])
            with self.assertRaises(BriefingRefused):
                await jobs.briefing(owner, action='start', request='that flight', discovery_id=key, choice=1)
            runner.fail = True
            failed = await jobs.briefing(owner, action='find_flights', request='JFK')
            self.assertEqual(failed['status'], 'unavailable')
            self.assertNotIn('private provider diagnostic', repr(failed))
            self.assertNotIn('discovery_id', failed)
            self.assertIn('could not complete', discovery_notice(failed))
        finally:
            await jobs.close()

    def test_partial_and_full_search_speech_preserve_limits_and_computed_estimate(self):
        value = SearchRunner().find_flights('New York')
        text = discovery_notice(value)
        self.assertIn('United Airlines 57', text)
        self.assertIn('computed from position and speed', text)
        self.assertIn('2026-10-22', text)
        value['partial'] = True
        self.assertIn('some flights', discovery_notice(value))
        self.assertIn('search is partial', discovery_notice(value))
        value.update(status='no_results', candidates=[])
        self.assertNotIn('No matching', discovery_notice(value))
        value['partial'] = False
        self.assertIn('covered routes', discovery_notice(value))
