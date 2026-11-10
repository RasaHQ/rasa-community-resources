"""The reply is later in both variants; only next-turn binding rejects reuse."""
import importlib.util
from pathlib import Path
import unittest


class ConfirmationReplay(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        path = Path(__file__).resolve().parents[1] / 'mantle/demo_confirmation.py'
        spec = importlib.util.spec_from_file_location('confirmation_replay', path)
        self.demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.demo)

    async def test_same_later_yes_is_refused_after_intervening_user_turn(self):
        previous = await self.demo.replay(timestamp_only=True)
        checked = await self.demo.replay(timestamp_only=False)
        self.assertEqual(previous['events'], checked['events'])
        self.assertEqual(checked['events'][-1]['text'], 'Yes')
        self.assertGreater(checked['events'][-1]['timestamp'], checked['proposal_created_from_event'])
        self.assertEqual(previous['read_status'], 'transactions')
        # Independent fingerprint of tools.py in the public c6eb50a revision.
        self.assertEqual(previous['tool_source_sha256'],
                         '9432b0b3ad1f340bb77b8565e3c93642003a20686487355bd1dd17293a4fab74')
        self.assertEqual(previous['account_reads'], ['A-CURRENT'])
        self.assertEqual(checked['read_status'], 'proposal_expired')
        self.assertEqual(checked['account_reads'], [])
        for result in [previous, checked]:
            self.assertEqual(result['scripted_sdk_requests'], 1)
            self.assertEqual(result['external_provider_requests'], 0)

    async def test_next_user_yes_can_still_confirm(self):
        result = await self.demo.replay(intervening=False)
        self.assertEqual(result['read_status'], 'transactions')
        self.assertEqual(result['account_reads'], ['A-CURRENT'])
        self.assertEqual(len([e for e in result['events'] if e['kind'] == 'user']), 2)
        self.assertEqual(result['scripted_sdk_requests'], 1)
