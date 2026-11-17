"""The process-exit control retains diagnostics on the failure it detects."""
from pathlib import Path
import sys
import unittest
from child_exit_control import require_process_exit


class ChildExitTests(unittest.IsolatedAsyncioTestCase):
    async def test_marker_then_diagnostic_then_hang_fails_with_retained_stack(self):
        command = [sys.executable, '-u', '-c',
            "import time; print('AGENT_CLOSE_COMPLETE'); print('SYNTHETIC_STACK_DIAGNOSTIC'); time.sleep(30)"]
        with self.assertRaisesRegex(AssertionError, 'SYNTHETIC_STACK_DIAGNOSTIC'):
            await require_process_exit(command, cwd=Path.cwd(), ready_seconds=5, exit_seconds=0.2)

    async def test_marker_normal_exit_and_error_exit_retained(self):
        for code in (0, 17):
            observed, text = await require_process_exit([sys.executable, '-u', '-c',
                f"print('AGENT_CLOSE_COMPLETE'); raise SystemExit({code})"], cwd=Path.cwd())
            self.assertEqual(observed, code)
            self.assertIn('AGENT_CLOSE_COMPLETE', text)
