"""The per-resource Codespaces configurations are generated, complete and consistent."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_codespaces as g  # noqa: E402
from rasa_projects import REPO_ROOT, discover_projects  # noqa: E402


class GeneratedFilesTests(unittest.TestCase):
    def test_nothing_is_missing_or_stale(self):
        stale = [path for path, content in g.plan()
                 if not path.is_file() or path.read_text(encoding="utf-8") != content]
        self.assertEqual(stale, [], "run python3 scripts/generate_codespaces.py")

    def test_every_catalog_project_has_a_configuration_and_one_button(self):
        for project in discover_projects("catalog"):
            config = REPO_ROOT / ".devcontainer" / g.slug(project.rel) / "devcontainer.json"
            self.assertTrue(config.is_file(), project.rel)
            readme = (project.path / "README.md").read_text(encoding="utf-8")
            self.assertEqual(readme.count("Open in GitHub Codespaces"), 1, project.rel)
            self.assertIn(g.slug(project.rel) + "/devcontainer.json", readme)

    def test_manual_resources_are_covered(self):
        for item in g.MANUAL:
            self.assertTrue((REPO_ROOT / ".devcontainer" / g.slug(item["path"]) / "devcontainer.json").is_file())
            self.assertIn(g.START, (REPO_ROOT / item["path"] / "README.md").read_text(encoding="utf-8"))

    def test_configurations_share_one_image_and_declare_only_known_secrets(self):
        for entry in [g.manifest(p) for p in discover_projects("catalog")] + [g.manual_manifest(m) for m in g.MANUAL]:
            body = json.loads(g.config(entry))
            self.assertEqual(body["build"]["dockerfile"], "../resource-base/Dockerfile")
            self.assertIn("RASA_LICENSE", body["secrets"])
            self.assertLessEqual(set(body["secrets"]), set(g.KNOWN_SECRETS))
            self.assertTrue(body["workspaceFolder"].endswith("/" + entry["path"]))
            self.assertIn("ready.sh", body["postCreateCommand"])

    def test_license_alias_is_set_for_resources_that_read_the_older_name(self):
        aliased = [g.manifest(p)["path"] for p in discover_projects("catalog") if g.manifest(p)["alias_license"]]
        self.assertTrue(aliased)
        for path in aliased:
            body = json.loads((REPO_ROOT / ".devcontainer" / g.slug(path) / "devcontainer.json").read_text())
            self.assertIn("alias-license", body["onCreateCommand"])
            self.assertNotIn(g.LICENSE_ALIAS, body["secrets"])


class ParsingTests(unittest.TestCase):
    def test_required_and_optional_come_from_the_section_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".env.example").write_text(
                "# Required - license\nRASA_LICENSE=\n# Required - LLM\nOPENAI_API_KEY=\n"
                "# Optional - voice\nDEEPGRAM_API_KEY=\n",
                encoding="utf-8",
            )
            self.assertEqual(
                g.env_example_secrets(Path(directory)),
                {"RASA_LICENSE": True, "OPENAI_API_KEY": True, "DEEPGRAM_API_KEY": False},
            )

    def test_block_replacement_is_stable(self):
        block = g.START + "\nx\n" + g.END
        text = "# Title\n\nbody\n"
        once = g.with_block(text, block)
        self.assertEqual(g.with_block(once, block), once)
        self.assertEqual(once.count(g.START), 1)


if __name__ == "__main__":
    unittest.main()
