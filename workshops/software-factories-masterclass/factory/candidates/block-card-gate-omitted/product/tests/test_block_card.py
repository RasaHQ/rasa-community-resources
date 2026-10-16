"""The builder's own tests. A candidate may add them. The factory records the result and never trusts it."""
import os
import unittest
from pathlib import Path

from rasa.mantle.skills.markdown_skill_compiler import compile_markdown_skill
from rasa.mantle.validation import collect_project_findings

PROJECT = Path(os.environ["MANTLE_PROJECT"])


class BlockCardTests(unittest.TestCase):
    def test_the_project_validates(self):
        self.assertEqual(collect_project_findings(PROJECT), [])

    def test_the_skill_compiles_under_its_own_name(self):
        skill = compile_markdown_skill(PROJECT / "skills" / "block_card" / "skill.md")
        self.assertEqual(skill.id, "block_card")


if __name__ == "__main__":
    unittest.main()
