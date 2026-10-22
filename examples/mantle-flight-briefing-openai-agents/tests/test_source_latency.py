"""Offline blocking-read timing: no provider, key or paid model request."""
from pathlib import Path
from threading import Barrier, Lock
from types import SimpleNamespace
import sys
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.live_public_sources import LivePublicSourcesRunner
from briefing.jobs import Work


class ConcurrentSourceLatency(unittest.TestCase):
    def test_one_selected_native_tool_overlaps_four_blocking_reads(self):
        barrier = Barrier(4, timeout=2)
        seen = []
        lock = Lock()
        class Client:
            beta = SimpleNamespace(agents=SimpleNamespace(sessions=SimpleNamespace(create=lambda: None)))
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def invoke(client, **kwargs):
            self.assertEqual(set(kwargs['handlers']), {'read_briefing'})
            self.assertEqual(kwargs['max_calls'], 1)
            result = kwargs['handlers']['read_briefing']({})
            self.assertEqual(set(result), {'flight', 'weather', 'rate', 'timeline'})
            return SimpleNamespace(ok=True)
        def recorded_read(component):
            def read(arguments):
                barrier.wait()  # Serial dispatch cannot satisfy this source control.
                with lock: seen.append(component)
                time.sleep(.1)  # Recorded equal latency, not a public endpoint.
                return {'recorded_component': component}
            return read
        runner = LivePublicSourcesRunner(Client, model='offline-timing-control',
            sources=SimpleNamespace(close=lambda: None), invoke=invoke)
        start = time.monotonic()
        result = runner._invoke(Work('controlled journey', 'offline-request', 1, None),
            [{'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}],
            {name: recorded_read(name) for name in ('flight', 'weather', 'rate', 'timeline')})
        elapsed = time.monotonic() - start
        self.assertTrue(result.ok)
        self.assertEqual(len(seen), 4)
        self.assertLess(elapsed, .35, 'Four .1s recorded reads must overlap, not add to .4s')
        print(f'recorded_four_read_seconds={elapsed:.4f}; serial_control_seconds=0.4')

    def test_pending_refresh_progress_preserves_old_validated_cards(self):
        from briefing.board_display import progress_document
        old = '<html><body><article>Validated flight and meeting</article></body></html>'
        shown = progress_document(old, 'Checking the flight... the weather... the rate...')
        self.assertIn('<p role="status">Checking the flight', shown)
        self.assertIn('<article>Validated flight and meeting</article>', shown)
        self.assertEqual(progress_document(old, 'Ready for another briefing.'), old)
