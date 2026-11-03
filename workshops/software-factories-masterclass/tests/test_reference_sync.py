"""The shipped reference agent embeds travel_data.py; the two must not drift apart."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReferenceSyncTests(unittest.TestCase):
    def test_reference_tools_start_with_the_current_readers(self):
        head = (ROOT / "travel_data.py").read_text().split("if __name__")[0]
        tools = (ROOT / "reference/finished-agent/skills/travel_briefing/tools.py").read_text()
        self.assertTrue(tools.startswith(head), "regenerate reference tools.py from travel_data.py")


if __name__ == "__main__":
    unittest.main()
