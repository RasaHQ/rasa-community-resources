"""Ensure deliberately weakened replay/network guards fail their controls."""
import io
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import test_refusal_exit as exits
import test_refusal_network as network


class MutationControls(unittest.TestCase):
    def test_guard_removals_are_detected(self):
        path = Path(__file__).resolve().parents[1] / "replay.py"
        source = path.read_text()
        cases = [
            (' and call["result"].get("status") == "refused"', '',
             exits.ReplayControls, "test_initial_request_must_actually_be_refused"),
            ('if refused != 0:', 'if False:',
             exits.ReplayControls, "test_another_business_tool_cannot_precede_refusal"),
            ('if event.get("is_error"):', 'if False:',
             exits.ReplayControls, "test_runtime_errors_and_malformed_results_are_rejected"),
            ('if any(call["name"] != "record_demo_handoff" for call in later):', 'if False:',
             exits.ReplayControls, "test_unknown_successful_tool_is_not_an_exit"),
            ('len(handoffs) != 1', 'False', exits.ReplayControls, "test_two_handoffs_are_not_one"),
            (' or handoffs[0]["result"].get("status") != "demo_handoff"', '',
             exits.ReplayControls, "test_handoff_status_and_reference_are_required"),
            ('\n            or handoffs[0]["result"].get("reference") != "HANDOFF-DEMO"', '',
             exits.ReplayControls, "test_handoff_status_and_reference_are_required"),
            ('if raw != name + ": done":', 'if False:',
             exits.ReplayControls, "test_premature_completion_or_bad_control_result_is_rejected"),
            ('elif not any(call["name"] == "record_demo_handoff" for call in calls):', 'elif False:',
             exits.ReplayControls, "test_premature_completion_or_bad_control_result_is_rejected"),
            ('urllib.request.ProxyHandler({})', 'urllib.request.ProxyHandler()',
             network.NetworkControls, "test_chat_and_tracker_ignore_inherited_proxy"),
            (', NoRedirects()', '', network.NetworkControls, "test_chat_and_tracker_never_follow_redirects"),
        ]
        for old, new, control, name in cases:
            with self.subTest(guard=old):
                self.assertEqual(source.count(old), 1, "Refresh mutation for changed source")
                mutant = types.ModuleType("mutated_replay")
                exec(compile(source.replace(old, new, 1), str(path), "exec"), mutant.__dict__)
                with patch.object(exits, "validate_tracker", mutant.validate_tracker), \
                     patch.object(exits, "validate_episode", mutant.validate_episode), \
                     patch.object(network, "local_json", mutant.local_json):
                    result = unittest.TextTestRunner(stream=io.StringIO()).run(
                        unittest.TestSuite([control(name)]))
                self.assertTrue(result.failures, "Control must reject the weakened guard")
                self.assertFalse(result.errors, "Import/runtime errors are not mutation proof")
