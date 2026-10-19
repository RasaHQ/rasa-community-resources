"""Process transport tests, not a replacement for Core's byte validator."""

from pathlib import Path
import sys
import tempfile
import unittest

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
            self.invoke("raise SystemExit(2)\n")
        with self.assertRaises(RuntimeError) as caught:
            self.invoke("raise SystemExit(1)\n")
        self.assertNotIsInstance(caught.exception, CanonicalRefusal)

    def test_invalid_normalized_output_is_not_a_schema_refusal(self):
        with self.assertRaises(ValueError) as caught:
            self.invoke("print('not JSON')\n")
        self.assertNotIsInstance(caught.exception, CanonicalRefusal)

    def test_transport_keeps_wire_alias_and_partial_flag(self):
        value = self.invoke('print(\'{"schema":"zeo.ui-result/v1","complete":false}\')\n')
        self.assertEqual(value["schema"], "zeo.ui-result/v1")
        self.assertIs(value["complete"], False)
