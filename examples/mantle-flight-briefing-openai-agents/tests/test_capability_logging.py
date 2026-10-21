"""Log privacy for the explicitly approved capability-id fallback."""
import io
import importlib.util
from contextlib import redirect_stdout
import logging
from pathlib import Path
import secrets
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project.lib.capability_logging import install


class CapabilityLogging(unittest.TestCase):
    def test_capability_is_redacted_before_log_formatting(self):
        install()
        capability = "brf_" + secrets.token_urlsafe(32)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("briefing.privacy.control")
        logger.addHandler(handler)
        try:
            logger.warning("A capability must not appear: %s", capability)
        finally:
            logger.removeHandler(handler)
        self.assertNotIn(capability, stream.getvalue())
        self.assertIn("[briefing capability redacted]", stream.getvalue())

    @unittest.skipUnless(importlib.util.find_spec("structlog"), "structured logging belongs to the Mantle project environment")
    def test_structured_console_arguments_are_redacted(self):
        import structlog
        install()
        capability = "brf_" + secrets.token_urlsafe(32)
        stream = io.StringIO()
        with redirect_stdout(stream):
            structlog.get_logger("briefing.privacy.structured").warning(
                "tool arguments", arguments={"briefing_id": capability})
        self.assertNotIn(capability, stream.getvalue())
        self.assertIn("[briefing capability redacted]", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
