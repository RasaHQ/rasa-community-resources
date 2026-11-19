"""Registered candidate releases must not drift or migrate with the catalog."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import rasa_projects as resources
import lint_repo


class ReleaseProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        self.rel = "tutorials/speech-week/silverlake-deepgram"
        self.project = self.root / self.rel
        self.project.mkdir(parents=True)
        (self.project / "pyproject.toml").write_text(
            '[project]\nname="profile"\nversion="0.1"\ndependencies=["rasa-pro==3.22.0rc1"]\n'
            '[tool.rasa-catalog]\nrelease-version="3.22.0rc1"\n[tool.uv]\nprerelease="allow"\n')
        (self.project / "uv.lock").write_text('[[package]]\nname = "rasa-pro"\nversion = "3.22.0rc1"\n')
        (self.root / "scripts/release-profiles.json").write_text(json.dumps({"schema":1,"profiles":{
            self.rel: {"version":"3.22.0rc1","ruling":"fixture-approval"}}}))
        self.guard = patch.object(resources, "REPO_ROOT", self.root)
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_scoped_pin_does_not_leak_to_other_projects(self):
        self.assertEqual(resources.release_profile_version(self.project / "README.md"), "3.22.0rc1")
        self.assertIsNone(resources.release_profile_version("examples/ordinary"))
        self.assertIsNone(resources.release_profile_version(self.rel + "-other"))

    def test_metadata_alone_cannot_opt_out(self):
        data = self.project / "pyproject.toml"
        data.write_text(data.read_text().replace('release-version="3.22.0rc1"', 'release-version="3.22.0rc2"'))
        with self.assertRaises(ValueError):
            resources.release_profile_version(self.rel)

    def test_lock_drift_still_fails(self):
        project = resources.Project(self.project)
        self.assertTrue(resources.project_drift(project, "3.21.0.dev5").ok)
        (self.project / "uv.lock").write_text('[[package]]\nname = "rasa-pro"\nversion = "3.21.0.dev5"\n')
        self.assertFalse(resources.project_drift(project, "3.21.0.dev5").ok)
        with patch.object(lint_repo, "REPO_ROOT", self.root):
            self.assertTrue(lint_repo.check_lock_sync([project], "3.21.0.dev5"))

    def test_profile_prose_is_linted_against_its_own_pin(self):
        document = self.project / "README.md"
        document.write_text("Install rasa-pro==3.21.0.dev5.\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        with patch.object(lint_repo, "REPO_ROOT", self.root):
            self.assertTrue(lint_repo.check_version_consistency("3.21.0.dev5"))
            document.write_text("Install rasa-pro==3.22.0rc1.\n")
            self.assertFalse(lint_repo.check_version_consistency("3.21.0.dev5"))

    def test_tracked_candidate_inputs_are_excluded_from_catalog_migration(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        ordinary = self.root / "examples/ordinary/pyproject.toml"
        ordinary.parent.mkdir(parents=True)
        ordinary.write_text('[project]\nname="ordinary"\nversion="0.1"\ndependencies=["rasa-pro==3.21.0.dev5"]\n')
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        paths = resources.tracked_version_paths("**/pyproject.toml")
        self.assertEqual(paths, [ordinary])
