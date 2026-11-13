"""Offline check of the manual live text harness: no server, no model, no provider call.

It proves the harness keeps each assistant reply as evidence, next to the
pass or fail line, using fake replies instead of a running example.
"""
import contextlib
import io
import unittest
from unittest import mock

from tests import live_text_check as live


class FakeProcess:
    def __init__(self, *args, **kwargs):
        self.stdout = iter(["starting\n", "Rasa server is up and running.\n"])
        self.returncode = 0

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0


class HarnessKeepsReplies(unittest.TestCase):
    def run_with(self, checks, replies):
        out = io.StringIO()
        with mock.patch.object(live, "CHECKS", checks), \
                mock.patch.object(live.subprocess, "Popen", FakeProcess), \
                mock.patch.object(live, "say", side_effect=replies), \
                contextlib.redirect_stdout(out):
            code = live.main()
        return code, out.getvalue()

    def test_each_exact_reply_is_printed_under_its_result(self):
        code, text = self.run_with(
            [("a", "What accounts do I have?", ["DDA"], ["checking"]),
             ("a", "What is the balance of DDA-A?", ["not available"], ["USD"])],
            ["You have DDA account A.", "That is not available in this release."])
        self.assertEqual(code, 0)
        self.assertIn("ok   What accounts do I have?\n     reply: You have DDA account A.\n", text)
        self.assertIn("     reply: That is not available in this release.\n", text)
        self.assertIn("2/2 checks passed", text)

    def test_a_failing_reply_is_still_printed_verbatim(self):
        code, text = self.run_with([("a", "Balance?", ["not available"], ["USD"])],
                                   ["Your balance is USD 5.00."])
        self.assertEqual(code, 1)
        self.assertIn("FAIL Balance?", text)
        self.assertIn("     reply: Your balance is USD 5.00.\n", text)


if __name__ == "__main__":
    unittest.main()
