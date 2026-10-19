"""Process transport tests, not a replacement for Core's byte validator."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from lib.core_process import CanonicalRefusal, CoreProcess


class ProcessBoundaryTests(unittest.TestCase):
    def invoke(self, script):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bridge = root / "controlled-test-process.py"
            bridge.write_text(script)
            validator = CoreProcess(
                Path(sys.executable).resolve(), bridge,
                environment={"HOME": directory, "TMPDIR": directory},
            )
            return validator(b"synthetic input")

    def test_explicit_refusal_is_distinct_from_runtime_failure(self):
        with self.assertRaises(CanonicalRefusal):
            self.invoke("print('ZEO_UI_REFUSED_V1'); raise SystemExit(65)\n")
        with self.assertRaises(RuntimeError) as caught:
            self.invoke("raise SystemExit(1)\n")
        self.assertNotIsInstance(caught.exception, CanonicalRefusal)

    def test_exit_code_alone_and_missing_bridge_are_unavailable(self):
        for code in (2, 65):
            with self.assertRaisesRegex(RuntimeError, "canonical_validator_unavailable"):
                self.invoke(f"raise SystemExit({code})\n")
        with tempfile.TemporaryDirectory() as directory:
            validator = CoreProcess(
                Path(sys.executable).resolve(), Path(directory) / "missing.py",
                environment={"HOME": directory, "TMPDIR": directory},
            )
            with self.assertRaisesRegex(RuntimeError, "canonical_validator_unavailable"):
                validator(b"fixture")

    def test_stdout_cap_stops_an_unbounded_writer(self):
        with self.assertRaisesRegex(RuntimeError, "canonical_validator_output_bound"):
            self.invoke("import os\nwhile True: os.write(1, b'x' * 65536)\n")

    def test_bridge_timeout_is_unavailable_not_refusal(self):
        with patch("lib.core_process.VALIDATION_TIMEOUT_SECONDS", 0.05):
            with self.assertRaisesRegex(RuntimeError, "canonical_validator_timeout"):
                self.invoke("import time; time.sleep(10)\n")

    def test_invalid_normalized_output_is_not_a_schema_refusal(self):
        with self.assertRaises(ValueError) as caught:
            self.invoke("print('not JSON')\n")
        self.assertNotIsInstance(caught.exception, CanonicalRefusal)

    def test_transport_keeps_wire_alias_and_partial_flag(self):
        value = self.invoke('print(\'{"schema":"zeo.ui-result/v1","complete":false}\')\n')
        self.assertEqual(value["schema"], "zeo.ui-result/v1")
        self.assertIs(value["complete"], False)
