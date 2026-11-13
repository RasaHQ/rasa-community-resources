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

ROW_RE = re.compile(r"^\| \[(?P<title>.*?)\]\((?P<folder>[^)]+)/\) \| (?P<kind>[^|]+) \| .* \| \[Open\]\((?P<url>[^)]+)\) \|$")


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
            self.assertEqual(len(errors), 2)
            self.assertIn("examples/demo/README.md: add 'Industry: <Banking", errors[0])
            self.assertIn("after line 6", errors[0])
            self.assertIn("You learn", errors[1])

    def test_unknown_industry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_resource(root, "examples/demo", "Industry:      Aerospace\nYou learn:     How to fly.\n")
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
            fake_resource(root, "patterns/demo", "Industry:      General\nYou learn:     How to test.\n")
            rows, errors = c.collect(root, [{"path": "patterns/demo", "slug": "patterns-demo"}])
            self.assertEqual(errors, [])
            self.assertEqual(rows[0]["kind"], "pattern")
            self.assertEqual(rows[0]["title"], "A fake resource")
            self.assertEqual(rows[0]["url"], g.launch_url({"slug": "patterns-demo"}))

    def test_stale_section_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = [{"path": "patterns/demo", "slug": "patterns-demo"}]
            fake_resource(root, "patterns/demo", "Industry:      General\nYou learn:     How to test.\n")
            (root / "README.md").write_text(f"# Root\n\n{c.START}\nold\n{c.END}\n", encoding="utf-8")
            current, fresh = c.build(root, target)
            self.assertNotEqual(current, fresh)
            (root / "README.md").write_text(fresh, encoding="utf-8")
            current, fresh = c.build(root, target)
            self.assertEqual(current, fresh)

    def test_markers_are_required(self):
        with self.assertRaises(c.CatalogError):
            c.with_section("# Root\n", "section")


if __name__ == "__main__":
    unittest.main()
