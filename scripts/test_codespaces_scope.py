"""Which Codespace configurations the CI build covers on each kind of run."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codespaces_scope as scope

RES = [{"path": f"examples/{n}", "slug": f"examples-{n}"} for n in ("a", "b", "c", "d")]


class Choose(unittest.TestCase):
    def test_push_builds_only_the_changed_configs(self):
        self.assertEqual([r["slug"] for r in scope.choose("push", RES, {"examples-b"})], ["examples-b"])

    def test_push_with_no_config_change_builds_nothing(self):
        self.assertEqual(scope.choose("push", RES, set()), [])

    def test_push_ignores_a_name_that_is_not_a_resource(self):
        self.assertEqual(scope.choose("push", RES, {"no-such-slug"}), [])

    def test_schedule_and_pull_request_build_everything(self):
        for event in ("schedule", "pull_request"):
            self.assertEqual(scope.choose(event, RES, {"examples-a"}), RES)

    def test_manual_run_builds_everything_or_the_named_slugs(self):
        self.assertEqual(scope.choose("workflow_dispatch", RES, set()), RES)
        picked = scope.choose("workflow_dispatch", RES, set(), "examples-c  examples-a")
        self.assertEqual([r["slug"] for r in picked], ["examples-a", "examples-c"])


class ChangedSlugs(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.git("init", "-q")
        for rel in (".devcontainer/one/devcontainer.json", ".devcontainer/two/devcontainer.json",
                    ".devcontainer/resource-base/install.sh", "README.md"):
            self.write(rel, "x")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, check=True, capture_output=True, text=True).stdout

    def write(self, rel, text):
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self):
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "next")
        return self.git("rev-parse", "HEAD").strip()

    def changed(self, sha):
        original = scope.ROOT
        scope.ROOT = self.dir
        try:
            return scope.changed_slugs(self.base, sha)
        finally:
            scope.ROOT = original

    def test_one_config_edit_names_one_slug(self):
        self.write(".devcontainer/two/devcontainer.json", "y")
        self.assertEqual(self.changed(self.commit()), {"two"})

    def test_shared_base_and_other_files_name_no_slug(self):
        self.write(".devcontainer/resource-base/install.sh", "y")
        self.write("README.md", "y")
        self.assertEqual(self.changed(self.commit()), set())

    def test_a_new_push_with_no_before_commit_names_nothing(self):
        self.assertEqual(scope.changed_slugs("0" * 40, self.base), set())


class Real(unittest.TestCase):
    def test_the_real_list_is_resources_with_a_path_and_slug(self):
        resources = scope.every_resource()
        self.assertGreater(len(resources), 60)
        self.assertTrue(all(set(r) == {"path", "slug"} for r in resources))

    def test_the_workshop_configuration_is_in_the_list(self):
        self.assertIn("travel-factory", [r["slug"] for r in scope.every_resource()])
        for r in scope.every_resource():
            self.assertTrue((scope.ROOT / ".devcontainer" / r["slug"] / "devcontainer.json").is_file(), r)


if __name__ == "__main__":
    unittest.main()
