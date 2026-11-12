"""Regress the path-dependency ordering and fail-closed root pin update."""
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
import rasa_projects
import lint_repo
from unittest.mock import patch
import subprocess
import migrate_rasa_pro as migration


class MigrationOrderTests(unittest.TestCase):
    def test_lock_failure_keeps_the_conflicting_requirements_before_uv_hint(self):
        explanation = ('rasa-pro==3.22.0.dev3 requires mcp>=1.30.0,<1.31.0\n'
                       'project requires mcp==1.28.1\n'
                       'No solution exists.\n\n'
                       'hint: another platform was being resolved\n'
                       'consider limiting environments\n')
        failed = subprocess.CompletedProcess([], 1, stdout='', stderr=explanation)
        with patch.object(migration.shutil, 'which', return_value='uv'), patch.object(migration.subprocess, 'run', return_value=failed):
            with self.assertRaisesRegex(RuntimeError, 'mcp>=1.30.0,<1.31.0') as error:
                migration._run_uv_lock(Path('/tmp/project'), '3.22.0.dev3')
        self.assertIn('mcp==1.28.1', str(error.exception))
        self.assertIn('consider limiting environments', str(error.exception))

    def exercise(self, fail=False):
        projects=[SimpleNamespace(path=Path('/tmp/a'),rel='a'),SimpleNamespace(path=Path('/tmp/b'),rel='b')]
        prepared=[];resolved=[]
        def prepare(project,version,**kwargs):
            self.assertTrue(kwargs['skip_lock']);prepared.append(project.rel)
            return dict(error=None,path=project.rel,prerelease=None,docs=[],locked=False,pin_changed=True)
        def lock(path,version,**kwargs):
            self.assertEqual(prepared,['a','b']);resolved.append(path.name)
            if fail:raise RuntimeError('fixture resolver failure')
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(migration.sys,'argv',['migrate','--version','3.20.0.dev9','--no-touch-assessed-on']))
            for name,value in [('resolve_target',('3.20.0.dev9',True)),('verify_on_index',None),('verify_engine_support',None),('read_pyproject_pin','3.20.0.dev6'),('read_lock_version','3.20.0.dev9'),('_rewrite_doc',False)]:stack.enter_context(patch.object(migration,name,return_value=value))
            stack.enter_context(patch.object(migration,'discover_projects',side_effect=[projects,[]]))
            stack.enter_context(patch.object(migration,'additional_migration_projects',return_value=[]))
            stack.enter_context(patch.object(migration,'migrate_project',side_effect=prepare))
            stack.enter_context(patch.object(migration,'_run_uv_lock',side_effect=lock))
            stack.enter_context(patch.object(migration.subprocess,'check_output',return_value=b''))
            write=stack.enter_context(patch.object(migration,'write_version_file'))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            code=migration.main()
            if fail:self.assertEqual(code,1);write.assert_not_called()
            else:self.assertEqual(code,0);write.assert_called_once_with('3.20.0.dev9')
        self.assertEqual(resolved,['a','b'])
    def test_every_manifest_precedes_any_lock(self):self.exercise()
    def test_lock_failure_never_advances_root_pin(self):self.exercise(fail=True)

class NestedMigrationTests(unittest.TestCase):
    def test_tracked_nested_inputs_migrate_without_rewriting_history_or_catalog(self):
        old, new = '3.21.0.dev5', '3.22.0.dev3'
        workshop = 'workshops/software-factories-masterclass/'
        active = ['examples/mantle-factory-agent/project',
                  'examples/mantle-flight-briefing-openai-agents/project',
                  workshop + 'env']
        frozen = [workshop + 'archive/2026-10-22-original/project',
                  workshop + 'factory', workshop + 'openai-mcp',
                  'heroes/wave-01/projects/receipt']
        stable = workshop + 'book/ready/ch00/demo/project'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            for rel in active + frozen + [stable]:
                target = root / rel / 'pyproject.toml'
                target.parent.mkdir(parents=True)
                marker = ' # rasa-version-ignore: qualified stable runtime' if rel == stable else ''
                target.write_text('[project]\nname = "fixture"\nversion = "0.1.0"\ndependencies = [\n'
                                  f'  "rasa-pro=={old}",{marker}\n]\n')
            doc = root / 'tutorials/voice-agent-three-frameworks/shared/web/PROTOCOL.md'
            doc.parent.mkdir(parents=True)
            doc.write_text(f'Install rasa-pro=={old}.\n')
            historical = root / frozen[0] / 'README.md'
            historical.write_text(f'Verified with rasa-pro {old}\n')
            subprocess.run(['git', '-C', tmp, 'add', '.'], check=True)
            before = {rel: (root / rel / 'pyproject.toml').read_bytes() for rel in frozen + [stable]}
            with patch.object(rasa_projects, 'REPO_ROOT', root), patch.object(migration, 'REPO_ROOT', root):
                extra = rasa_projects.additional_migration_projects([])
                self.assertEqual({p.rel for p in extra}, set(active))
                self.assertEqual(rasa_projects.additional_migration_projects(extra), [])
                for project in extra:
                    result = migration.migrate_project(project, new, skip_lock=True,
                        touch_assessed_on=False, dry_run=False)
                    self.assertIsNone(result['error'])
                docs = rasa_projects.tracked_version_paths('*.md')
                self.assertEqual(docs, [doc])
                for path in docs:
                    migration._rewrite_doc(path, None, new, touch_assessed_on=False, dry_run=False)
            for rel in active:
                self.assertIn(new, (root / rel / 'pyproject.toml').read_text())
            for rel, content in before.items():
                self.assertEqual((root / rel / 'pyproject.toml').read_bytes(), content)
            self.assertIn(new, doc.read_text())
            self.assertIn(old, historical.read_text())

    def test_only_explicit_history_is_exempt_from_current_version_lint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ['workshops/software-factories-masterclass/env/pyproject.toml',
                     'workshops/software-factories-masterclass/archive/old/README.md',
                     'workshops/software-factories-masterclass/factory/README.md',
                     'workshops/software-factories-masterclass/openai-mcp/README.md']
            paths = [root / name for name in names]
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('rasa-pro==3.21.0.dev5\n')
            with patch.object(lint_repo, 'REPO_ROOT', root), patch.object(lint_repo, '_tracked_files', return_value=paths):
                findings = lint_repo.check_version_consistency('3.22.0.dev3')
            self.assertEqual([f.path for f in findings], [names[0]])

class HistoricalReadmeDriftTests(unittest.TestCase):
    OLD = "3.21.0.dev5"
    NEW = "3.22.0.dev3"

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / "patterns/mcp-confirmation-gate"
        self.folder.mkdir(parents=True)
        replacement = patch.object(rasa_projects, "REPO_ROOT", self.root)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.project = rasa_projects.Project(self.folder)
        self.manifest(self.OLD)
        self.lock(self.NEW)

    def manifest(self, version):
        (self.folder / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n'
            f'dependencies = ["rasa-pro=={version}"]\n'
            '[tool.uv]\nprerelease = "allow"\n')

    def lock(self, version):
        (self.folder / "uv.lock").write_text(
            f'[[package]]\nname = "rasa-pro"\nversion = "{version}"\n')

    def test_migrated_project_keeps_assessment_without_false_readme_drift(self):
        historical = ("Assessed on: 2026-10-15\n"
                      f"Verified with: rasa-pro {self.OLD}, Python 3.12 "
                      "# rasa-version-ignore: historical assessment\n")
        readme = self.folder / "README.md"
        readme.write_text(historical)
        result = migration.migrate_project(self.project, self.NEW, skip_lock=True,
                    touch_assessed_on=False, dry_run=False)
        self.assertIsNone(result["error"])
        self.assertEqual(readme.read_text(), historical)
        self.assertIsNone(rasa_projects.read_readme_verified(self.project))
        drift = rasa_projects.project_drift(self.project, self.NEW)
        self.assertTrue(drift.ok, drift.issues())

    def test_unmarked_stale_assessment_still_blocks(self):
        self.manifest(self.NEW)
        (self.folder / "README.md").write_text(f"Verified with: rasa-pro {self.OLD}\n")
        drift = rasa_projects.project_drift(self.project, self.NEW)
        self.assertFalse(drift.ok)
        self.assertEqual(drift.readme, self.OLD)

    def test_current_installation_takes_precedence_over_marked_history(self):
        (self.folder / "README.md").write_text(
            f"Verified with: rasa-pro {self.OLD} # rasa-version-ignore: history\n"
            f"Installation: rasa-pro {self.OLD}\n")
        migration.migrate_project(self.project, self.NEW, skip_lock=True,
                                  touch_assessed_on=False, dry_run=False)
        self.assertEqual(rasa_projects.read_readme_verified(self.project), self.NEW)
        self.assertIn(f"Verified with: rasa-pro {self.OLD}",
                      (self.folder / "README.md").read_text())

    def test_marked_installation_is_checked_and_migrated_as_current(self):
        for prefix in ("  ", "- ", "> "):
            with self.subTest(prefix=prefix):
                self.manifest(self.NEW)
                readme = self.folder / "README.md"
                readme.write_text(f"{prefix}Installation: rasa-pro {self.OLD} "
                                  "# rasa-version-ignore: must not hide the current pin\n")
                self.assertEqual(rasa_projects.read_readme_verified(self.project), self.OLD)
                self.assertFalse(rasa_projects.project_drift(self.project, self.NEW).ok)
                with patch.object(lint_repo, "REPO_ROOT", self.root), \
                     patch.object(lint_repo, "_tracked_files", return_value=[readme]):
                    self.assertTrue(lint_repo.check_version_consistency(self.NEW))
                    result = migration.migrate_project(self.project, self.NEW, skip_lock=True,
                                        touch_assessed_on=False, dry_run=False)
                    self.assertIsNone(result["error"])
                    self.assertEqual(lint_repo.check_version_consistency(self.NEW), [])
                self.assertEqual(rasa_projects.read_readme_verified(self.project), self.NEW)
                self.assertTrue(rasa_projects.project_drift(self.project, self.NEW).ok)
                self.assertIn("rasa-version-ignore", readme.read_text())

    def test_history_marker_never_exempts_manifest_or_lock_drift(self):
        (self.folder / "README.md").write_text(
            f"Verified with: rasa-pro {self.OLD} # rasa-version-ignore: history\n")
        for manifest, lock in ((self.OLD, self.NEW), (self.NEW, self.OLD)):
            with self.subTest(manifest=manifest, lock=lock):
                self.manifest(manifest)
                self.lock(lock)
                drift = rasa_projects.project_drift(self.project, self.NEW)
                self.assertFalse(drift.ok)
                self.assertTrue(any(issue.startswith(("pyproject=", "lock="))
                                    for issue in drift.issues()))


class TrainingCredentialsTests(unittest.TestCase):
    def test_runtime_key_is_not_mistaken_for_a_local_training_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);project=rasa_projects.Project(path)
            manifest=path/'pyproject.toml'
            manifest.write_text('[tool.rasa-catalog]\nrequired-secrets = ["GEMINI_API_KEY"]\ntraining-secrets = []\n')
            self.assertEqual(rasa_projects.read_required_secrets(project), ['GEMINI_API_KEY'])
            self.assertEqual(rasa_projects.read_training_secrets(project), [])
            manifest.write_text('[tool.rasa-catalog]\nrequired-secrets = ["OPENAI_API_KEY"]\n')
            self.assertEqual(rasa_projects.read_training_secrets(project), ['OPENAI_API_KEY'])

if __name__=='__main__':unittest.main()
