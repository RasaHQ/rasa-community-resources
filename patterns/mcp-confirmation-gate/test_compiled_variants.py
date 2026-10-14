"""Native compilation control only; no full runtime or model call."""
import tempfile
import unittest
from pathlib import Path

from rasa.mantle.skills.catalog import SkillCatalog
from rasa.mantle.skills.conditions import is_confirmation_gate_active
from rasa.mantle.skills.markdown_skill_compiler import compile_markdown_skill


class CompiledVariants(unittest.TestCase):
    def test_only_confirmation_flag_differs_and_native_catalog_preserves_it(self):
        template = Path(__file__).with_name("skill.md.in").read_text()
        self.assertEqual(template.count("CONFIRMATION_ENABLED"), 1)
        sources = {name: template.replace("CONFIRMATION_ENABLED", flag)
                   for name, flag in (("gated", "true"), ("ungated", "false"))}
        self.assertEqual(sources["gated"].replace("enabled: true", "enabled: false"),
                         sources["ungated"])
        imports = []
        with tempfile.TemporaryDirectory() as temp:
            for name, source in sources.items():
                path = Path(temp) / name / "review_case" / "skill.md"
                path.parent.mkdir(parents=True)
                path.write_text(source)
                skill = compile_markdown_skill(path)
                self.assertEqual(skill.import_tool_names,
                                 frozenset({"mcp/fictional_support:read_case"}))
                catalog = SkillCatalog(skills={skill.id: skill})
                constraint = catalog.effective_tool_gate(skill.id, "", "record_local_canary")
                self.assertIsNotNone(constraint)
                self.assertEqual(is_confirmation_gate_active(constraint.requires_confirmation),
                                 name == "gated")
                imports.append(skill.import_tool_names)
        self.assertEqual(imports[0], imports[1])


if __name__ == "__main__":
    unittest.main()
