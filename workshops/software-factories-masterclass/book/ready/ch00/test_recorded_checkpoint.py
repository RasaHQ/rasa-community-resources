"""Recorded changes traverse the real Jobs/Core path with sockets refused.
sow: software-factories-masterclass-SOW-02
"""
import asyncio
import socket
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'demo'))
from briefing.jobs import Jobs, Owner
from check_demo import inspect_cards
from recorded_checkpoint import load_recording, make_runner
from zeo_core.adapters.widget_html import render_card_html, render_snapshot_html


class RecordedControls(unittest.IsolatedAsyncioTestCase):
    async def test_recorded_change_requires_no_source_connection_and_changes_only_planning(self):
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
            runner = make_runner()
            jobs = Jobs(runner, replacement_plan=runner.replacement_plan, ownership_mode='capability')
            owner = Owner('offline-test', 'single-controlled-conversation')
            try:
                result = await jobs.briefing(owner, action='start', request='United 1162 to EWR')
                job = result['job_id']

                async def settled():
                    for _ in range(100):
                        value = await jobs.briefing(owner, action='get', job_id=job)
                        if value['status'] not in ('started', 'running'):
                            return value
                        await asyncio.sleep(.01)
                    self.fail('recorded job did not finish')

                self.assertEqual((await settled())['status'], 'needs_input')
                await jobs.briefing(owner, action='revise', job_id=job, change='the 6 pm meeting tomorrow')
                self.assertEqual((await settled())['status'], 'complete')
                before = {state.component: state.data_ref for state in jobs.display_snapshot()}
                html = render_snapshot_html(jobs.display_snapshot(), document=True, place=jobs.display_place())
                self.assertTrue(inspect_cards(html, require_replay=True))
                for target in (30, 120):
                    self.assertFalse(inspect_cards(html, require_replay=True, transfer_minutes=target))
                    await jobs.briefing(owner, action='revise', job_id=job,
                                        change='allow ' + str(target) + ' minutes to get into town')
                    self.assertEqual((await settled())['status'], 'complete')
                    after = {state.component: state.data_ref for state in jobs.display_snapshot()}
                    self.assertTrue(all(reference.replay for reference in after.values()))
                    for component in ('flight_status', 'weather_hourly', 'market_watchlist'):
                        self.assertEqual(before[component].payload, after[component].payload)
                    self.assertEqual(before['arrival_timeline'].payload['meeting_time'], after['arrival_timeline'].payload['meeting_time'])
                    self.assertEqual(after['arrival_timeline'].payload['transfer_minutes']['value'], target)
                    self.assertEqual(after['arrival_timeline'].payload['margin_minutes'] - before['arrival_timeline'].payload['margin_minutes'], 90 - target)
                    html = render_snapshot_html(jobs.display_snapshot(), document=True, place=jobs.display_place())
                    self.assertTrue(inspect_cards(html, require_replay=True, transfer_minutes=target))
                    self.assertIn('Computed from recorded position', html)
            finally:
                await jobs.close()
                runner.close()

    async def test_real_renderer_requires_answer_content_in_every_card(self):
        import re
        _, states = load_recording()
        rendered = [render_card_html(state) for state in states]
        self.assertTrue(inspect_cards(''.join(rendered), require_replay=True))
        self.assertFalse(inspect_cards(''.join(
            '<article class="zc-card zc-' + state.component + '"></article>'
            for state in states), require_replay=True))
        for index, state in enumerate(states):
            with self.subTest(component=state.component):
                # Keep the real title/REPLAY badge and provenance while removing
                # the actual answer; decoration must not satisfy completion.
                heading = re.search(r'<h3>.*?</h3>', rendered[index], re.S).group()
                provenance = re.search(r'<p class="zc-attr">.*', rendered[index], re.S).group()
                empty = '<article class="zc-card zc-' + state.component + '">'
                for body in ('', '<p> \n </p>', heading + provenance):
                    changed = list(rendered)
                    changed[index] = empty + body + '</article>'
                    self.assertFalse(inspect_cards(''.join(changed), require_replay=True))
        all_empty = ''.join('<article class="zc-card zc-' + state.component + '">'
                            + re.search(r'<h3>.*?</h3>', html, re.S).group()
                            + '</article>' for state, html in zip(states, rendered))
        self.assertFalse(inspect_cards(all_empty, require_replay=True))

    async def test_replay_is_explicit_and_original_recording_is_not_rewritten(self):
        record, cards = load_recording()
        self.assertEqual(len(cards), 4)
        self.assertTrue(all(card.data_ref.replay for card in cards))
        self.assertTrue(all(not card['data_ref']['replay'] for card in record['cards']))
        runner = make_runner()
        try:
            result = runner.find_flights('New York')
            self.assertEqual(result['status'], 'needs_input')
            self.assertIn('replay', result['needs_input']['question'])
        finally:
            runner.close()


if __name__ == '__main__':
    unittest.main()
