import json
import tempfile
import unittest
from pathlib import Path

from agno.models.response import ModelResponse

from shop_adviser.native_fixture import ObservedModel
from shop_adviser.service import AdviserService


class UnusableAdvice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def answer(self, content=None, *, failed=False):
        class UnusableModel(ObservedModel):
            def invoke(self, messages, **kwargs):
                if failed:
                    raise RuntimeError("synthetic_provider_failure")
                if any(m.role == "tool" for m in messages):
                    return ModelResponse(role="assistant", content=content)
                return super().invoke(messages, **kwargs)

        service = AdviserService(Path(self.tmp.name) / "shop.sqlite", UnusableModel)
        return service.answer("willow-a-chat", "Product question")

    def test_unknown_product_from_native_run_is_withheld(self):
        result = self.answer(
            json.dumps({"product_id": "UNLISTED", "explanation": "Synthetic advice"})
        )
        self.assertEqual(result, {"status": "advice_unavailable"})

    def test_native_run_with_malformed_output_is_withheld(self):
        self.assertEqual(self.answer("invalid JSON"), {"status": "advice_unavailable"})

    def test_native_model_failure_returns_unavailable_without_raw_error(self):
        self.assertEqual(self.answer(failed=True), {"status": "advice_unavailable"})


if __name__ == "__main__":
    unittest.main()
