"""Run deterministic worklet queue controls when the optional Node tool exists."""
from pathlib import Path
import shutil
import subprocess
import unittest


class BrowserClockControls(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'optional Node audio-quantum controls')
    def test_rendered_queue_pending_marker_and_overlap_controls(self):
        script = Path(__file__).resolve().parents[1] / 'voice_latency_browser' / 'test-clock-worklet.cjs'
        result = subprocess.run(['node', str(script)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
