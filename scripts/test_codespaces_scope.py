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

    def test_push_with_a_shared_change_builds_everything(self):
        self.assertEqual(scope.choose("push", RES, None), RES)

    def test_push_ignores_a_name_that_is_not_a_resource(self):
        self.assertEqual(scope.choose("push", RES, {"no-such-slug"}), [])

    def test_schedule_builds_everything(self):
        for event in ("schedule",):
            self.assertEqual(scope.choose(event, RES, {"examples-a"}), RES)

    def test_pull_request_selects_affected_resources(self):
        self.assertEqual(scope.choose('pull_request', RES, {'examples-b'}), [RES[1]])
        self.assertEqual(scope.choose('pull_request', RES, set()), [])
        self.assertEqual(scope.choose('pull_request', RES, None), RES)

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
            return scope.changed_slugs(self.base, sha, [])
        finally:
            scope.ROOT = original

    def test_one_config_edit_names_one_slug(self):
        self.write(".devcontainer/two/devcontainer.json", "y")
        self.assertEqual(self.changed(self.commit()), {"two"})

    def test_a_shared_base_change_means_everything(self):
        self.write(".devcontainer/resource-base/install.sh", "y")
        self.assertIsNone(self.changed(self.commit()))

    def test_a_shared_base_change_beside_a_config_change_still_means_everything(self):
        self.write(".devcontainer/resource-base/install.sh", "y")
        self.write(".devcontainer/two/devcontainer.json", "y")
        self.assertIsNone(self.changed(self.commit()))

    def test_the_generator_the_scope_script_and_the_workflow_mean_everything(self):
        for rel in ("scripts/generate_codespaces.py", "scripts/codespaces_scope.py", ".github/workflows/codespaces-build.yml"):
            self.write(rel, "x")
            self.git("add", "-A")
            self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "add " + rel)
            base = self.git("rev-parse", "HEAD").strip()
            self.write(rel, "y")
            sha = self.commit()
            original = scope.ROOT
            scope.ROOT = self.dir
            try:
                self.assertIsNone(scope.changed_slugs(base, sha), rel)
            finally:
                scope.ROOT = original

    def test_unrelated_files_change_nothing(self):
        self.write("README.md", "y")
        self.assertEqual(self.changed(self.commit()), set())

    def test_resource_source_lock_and_transitive_dependency_select_the_consumer(self):
        resources = [{'path': 'examples/a', 'slug': 'a'}, {'path': 'examples/b', 'slug': 'b'}]
        self.write('examples/a/pyproject.toml', '[tool.uv.sources]\nshared = {path = "../shared"}\n')
        self.write('examples/shared/pyproject.toml', '[tool.uv.sources]\nleaf = {path = "../leaf"}\n')
        self.base = self.commit()
        for rel in ('examples/a/uv.lock', 'examples/a/tests/test_case.py', 'examples/leaf/lib.py'):
            self.write(rel, 'new')
            sha = self.commit()
            original = scope.ROOT
            scope.ROOT = self.dir
            try:
                self.assertEqual(scope.changed_slugs(self.base, sha, resources), {'a'})
            finally:
                scope.ROOT = original
            self.base = sha

    def test_pull_request_uses_merge_base_not_unrelated_new_main_changes(self):
        self.write('.devcontainer/two/devcontainer.json', 'pr-change')
        head = self.commit()
        self.git('checkout', '-q', '--detach', self.base)
        self.write('.devcontainer/resource-base/install.sh', 'main-only')
        base = self.commit()
        original = scope.ROOT
        scope.ROOT = self.dir
        try:
            self.assertEqual(scope.changed_slugs(base, head, [], pull_request=True), {'two'})
            self.assertIsNone(scope.changed_slugs('f' * 40, head, []))
        finally:
            scope.ROOT = original

    def test_a_new_push_with_no_before_commit_means_everything(self):
        self.assertIsNone(scope.changed_slugs("0" * 40, self.base))
        self.assertIsNone(scope.changed_slugs("", self.base))


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
