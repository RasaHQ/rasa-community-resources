"""Expose the documented controls to normal catalog test discovery."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromNames([
        "test_transport", "test_native_confirmation", "test_compiled_variants",
        "test_prepared_project", "test_cold_archives", "test_turn_loop",
        "test_http_turn_loop",
    ])
    if not suite.countTestCases():
        raise AssertionError("The MCP controls must not silently collect zero tests")
    return suite
