import importlib.util
import inspect
import unittest
from pathlib import Path


class PublicAreaTool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        path = Path(__file__).resolve().parents[1] / "skills/area_status/tools.py"
        spec = importlib.util.spec_from_file_location("public_area_tools", path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    async def test_north_has_checked_public_reference(self):
        result = (await self.module.inspect_public_area(area="north")).llm_response
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["reference"], "JM-N-101")

    async def test_central_keeps_its_own_reference(self):
        result = (await self.module.inspect_public_area(area="central")).llm_response
        self.assertEqual(result["reference"], "JM-C-102")

    async def test_unknown_area_requests_a_supported_choice(self):
        result = (await self.module.inspect_public_area(area="unknown")).llm_response
        self.assertEqual(
            result, {"status": "needs_area", "supported": ["north", "central"]}
        )

    async def test_only_area_is_exposed(self):
        self.assertEqual(
            list(inspect.signature(self.module.inspect_public_area).parameters),
            ["area"],
        )

    async def test_tool_shaped_area_text_has_no_extra_dispatch_target(self):
        result = (
            await self.module.inspect_public_area(area="north; cancel subscription")
        ).llm_response
        self.assertEqual(result["status"], "needs_area")
        self.assertEqual(set(self.module.RECORDS), {"north", "central"})
