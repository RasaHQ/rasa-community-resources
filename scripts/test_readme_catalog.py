"""The resource catalog in the root README is generated, complete and current."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_codespaces as g  # noqa: E402
import generate_readme_catalog as c  # noqa: E402
from rasa_projects import REPO_ROOT  # noqa: E402

NAME = "Catalog name:  Demo pattern for tests\n"
ROW_RE = re.compile(r"^\| \[(?P<name>.*?)\]\((?P<folder>[^)]+)/\) \| (?P<kind>[^|]+) \| .* \| \[Open\]\((?P<url>[^)]+)\) \|$")


def section_rows(text: str) -> list[re.Match]:
    section = text.split(c.START, 1)[1].split(c.END, 1)[0]
    return [m for m in (ROW_RE.match(line) for line in section.splitlines()) if m]


def fake_resource(root: Path, path: str, metadata: str) -> None:
    folder = root / path
    folder.mkdir(parents=True)
    (folder / "README.md").write_text(
        "# A fake resource\n\n```text\nAuthor:        Someone\nAssessed on:   2026-01-01\n"
        f"Verified with: rasa-pro 0\n{metadata}```\n\nBody.\n", encoding="utf-8")


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.rows = section_rows(self.readme)

    def test_every_codespaces_resource_appears_exactly_once(self):
        folders = [m["folder"] for m in self.rows]
        expected = [item["path"] for item in g.launch_matrix()]
        self.assertEqual(sorted(folders), sorted(expected))
        self.assertEqual(len(folders), len(set(folders)))

    def test_every_row_folder_exists_and_has_a_readme(self):
        for row in self.rows:
            self.assertTrue((REPO_ROOT / row["folder"] / "README.md").is_file(), row["folder"])

    def test_open_link_is_the_same_as_the_resource_button(self):
        for row in self.rows:
            readme = (REPO_ROOT / row["folder"] / "README.md").read_text(encoding="utf-8")
            self.assertIn(row["url"], readme, row["folder"])

    def test_kind_follows_the_folder(self):
        for row in self.rows:
            self.assertEqual(row["kind"], c.KIND_LABEL[c.kind_of(row["folder"])], row["folder"])
        self.assertEqual(c.kind_of("examples/fiserv-premier-11.0.0-prm"), "bank")
        self.assertEqual(c.kind_of("examples/mantle-voice-agent"), "voice")
        self.assertEqual(c.kind_of("examples/mantle-text-retail-loyalty-gpt"), "text")
        self.assertEqual(c.kind_of("heroes/wave-01-mantle/projects/x"), "heroes")

    def test_section_is_current(self):
        current, fresh = c.build()
        self.assertEqual(current, fresh, "run make readme-catalog")


class CheckTests(unittest.TestCase):
    def test_missing_metadata_names_the_file_and_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_resource(root, "examples/demo", "")
            rows, errors = c.collect(root, [{"path": "examples/demo", "slug": "examples-demo"}])
            self.assertEqual(rows, [])
            self.assertEqual(len(errors), 3)
            self.assertIn("examples/demo/README.md: add 'Industry: <Banking", errors[0])
            self.assertIn("after line 6", errors[0])
            self.assertIn("You learn", errors[1])
            self.assertIn("add 'Catalog name: <a short name, at most 60 characters>' after line 6", errors[2])

    def test_unknown_industry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_resource(root, "examples/demo", f"Industry:      Aerospace\nYou learn:     How to fly.\n{NAME}")
            _, errors = c.collect(root, [{"path": "examples/demo", "slug": "examples-demo"}])
            self.assertEqual(len(errors), 1)
            self.assertIn("examples/demo/README.md:7: Industry 'Aerospace' is not one of", errors[0])

    def test_missing_folder_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            _, errors = c.collect(Path(directory), [{"path": "examples/gone", "slug": "examples-gone"}])
            self.assertEqual(errors, ["examples/gone: folder does not exist"])

    def test_complete_metadata_makes_a_row_with_the_button_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_resource(root, "patterns/demo", f"Industry:      General\nYou learn:     How to test.\n{NAME}")
            rows, errors = c.collect(root, [{"path": "patterns/demo", "slug": "patterns-demo"}])
            self.assertEqual(errors, [])
            self.assertEqual(rows[0]["kind"], "pattern")
            self.assertEqual(rows[0]["name"], "Demo pattern for tests")
            self.assertEqual(rows[0]["url"], g.launch_url({"slug": "patterns-demo"}))

    def test_stale_section_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = [{"path": "patterns/demo", "slug": "patterns-demo"}]
            fake_resource(root, "patterns/demo", f"Industry:      General\nYou learn:     How to test.\n{NAME}")
            (root / "README.md").write_text(f"# Root\n\n{c.START}\nold\n{c.END}\n", encoding="utf-8")
            current, fresh = c.build(root, target)
            self.assertNotEqual(current, fresh)
            (root / "README.md").write_text(fresh, encoding="utf-8")
            current, fresh = c.build(root, target)
            self.assertEqual(current, fresh)

    def test_missing_catalog_name_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_resource(root, "patterns/demo", "Industry:      General\nYou learn:     How to test.\n")
            _, errors = c.collect(root, [{"path": "patterns/demo", "slug": "patterns-demo"}])
            self.assertEqual(len(errors), 1)
            self.assertIn("patterns/demo/README.md: add 'Catalog name:", errors[0])

    def test_failing_catalog_name_names_the_readme_and_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_resource(root, "patterns/demo", "Industry:      General\nYou learn:     How to test.\n"
                          "Catalog name:  Tool scope\n")
            _, errors = c.collect(root, [{"path": "patterns/demo", "slug": "patterns-demo"}])
            self.assertEqual(len(errors), 1)
            self.assertIn("patterns/demo/README.md:9: Catalog name 'Tool scope' has fewer than 3 words", errors[0])

    def test_only_work_in_progress_status_is_accepted_and_listed_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_resource(root, "patterns/demo", f"Industry:      General\nYou learn:     How to test.\n{NAME}"
                          "Status:        work in progress\n")
            fake_resource(root, "patterns/other", "Industry:      General\nYou learn:     How to test.\n"
                          "Catalog name:  Another demo pattern here\nStatus:        beta\n")
            rows, errors = c.collect(root, [{"path": "patterns/demo", "slug": "patterns-demo"},
                                            {"path": "patterns/other", "slug": "patterns-other"}])
            self.assertEqual(len(errors), 1)
            self.assertIn("patterns/other/README.md:10: Status 'beta' is not accepted", errors[0])
            section = c.render([r for r in rows if r["wip"]] + [dict(rows[1], wip=False)])
            main, wip = section.split("## Work in progress")
            self.assertNotIn("Demo pattern for tests", main)
            self.assertIn("Demo pattern for tests", wip)
            self.assertIn("There are 1 resources: 1 pattern. 1 more is still a work in progress", section)

    def test_bold_prose_status_sentence_is_not_metadata(self):
        fields = c.read_fields("# T\n\n**Status: all 21 conversations passed.**\n")
        self.assertNotIn("Status", fields)
        fields = c.read_fields("# T\n\n**Status:** work in progress\n")
        self.assertEqual(fields["Status"][0], "work in progress")

    def test_a_name_may_not_lead_with_a_command(self):
        problems = c.check_catalog_name("Build the Atlas voice travel agent step by step")
        self.assertTrue(any("starts with the command 'Build'" in p for p in problems), problems)
        self.assertEqual(c.check_catalog_name("Atlas voice travel agent tutorial, step by step"), [])
        self.assertEqual(c.check_catalog_name("Guarding card reissue to a new address"), [])
        self.assertEqual(c.check_catalog_name("How to build a voice travel agent"), [])
        self.assertFalse(any("command" in p for p in c.check_catalog_name("Which voice vendor handles failover?")))
        self.assertTrue(any("command" in p for p in c.check_catalog_name("Use Rime for voice banking")))

    def test_shared_openings_within_one_industry_are_limited(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets = []
            for n, name in enumerate(("Voice banking agent one", "Voice banking agent two", "Voice banking agent three")):
                fake_resource(root, f"patterns/p{n}", f"Industry:      General\nYou learn:     How.\nCatalog name:  {name}\n")
                targets.append({"path": f"patterns/p{n}", "slug": f"patterns-p{n}"})
            _, errors = c.collect(root, targets)
            self.assertEqual(len(errors), 1)
            self.assertIn("3 catalog names in the General table start with 'voice banking'", errors[0])

    def test_markers_are_required(self):
        with self.assertRaises(c.CatalogError):
            c.with_section("# Root\n", "section")


class CatalogNameRuleTests(unittest.TestCase):
    def test_a_good_name_passes(self):
        self.assertEqual(c.check_catalog_name("Bank advisor booking voice agent (Claude)"), [])

    def test_length_limit(self):
        self.assertIn("61 characters", c.check_catalog_name("Long name " + "x" * 51)[0])
        self.assertEqual(c.check_catalog_name("Long name " + "x" * 50), [])

    def test_confusing_shorthand_terms(self):
        for term in ("account boundary", "memory owner", "response owner"):
            problems = c.check_catalog_name(f"Voice agent {term} demo")
            self.assertTrue(any("shorthand" in p for p in problems), term)

    def test_generic_openings(self):
        for name in ("A guide to voice agents", "Best practices for agents", "Introduction to Rasa Mantle"):
            self.assertTrue(any("generic opening" in p for p in c.check_catalog_name(name)), name)

    def test_listicle_numbers(self):
        self.assertTrue(any("listicle" in p for p in c.check_catalog_name("5 ways to test agents")))

    def test_one_or_two_words_is_too_few(self):
        self.assertTrue(any("fewer than 3 words" in p for p in c.check_catalog_name("Banking demo")))
        self.assertTrue(any("fewer than 3 words" in p for p in c.check_catalog_name("Evaluation")))

    def test_trailing_punctuation(self):
        for name in ("Voice banking agent demo.", "Voice banking agent demo!", "Voice banking agent demo:"):
            self.assertTrue(any("punctuation" in p for p in c.check_catalog_name(name)), name)
        self.assertEqual(c.check_catalog_name("Voice banking agent demo (GPT)"), [])

    def test_names_are_unique(self):
        problems = c.check_catalog_name("Voice banking agent demo", ["voice banking agent demo"])
        self.assertTrue(any("already used" in p for p in problems))

    def test_every_real_name_passes_and_is_unique(self):
        rows, errors = c.collect()
        self.assertEqual(errors, [])
        names = [r["name"] for r in rows]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
