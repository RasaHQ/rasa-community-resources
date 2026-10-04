"""Regression checks for source-only copies and safe environment retirement."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('workspace', Path(__file__).with_name('workspace.py'))
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


class WorkspaceTests(unittest.TestCase):
    def test_retirement_receipts_are_not_application_source(self):
        path=Path(__file__).resolve().parents[1]/'tutorials/voice-agent-three-frameworks/shared/spec/count_concerns.py'
        spec=importlib.util.spec_from_file_location('tutorial_counter',path)
        counter=importlib.util.module_from_spec(spec);spec.loader.exec_module(counter)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'.rasa-environment-retired.json').write_text('{"owner":"test"}')
            (root/'application.json').write_text('{"setting":true}')
            (root/'agent.py').write_text('# concern: agent-logic\nanswer = 1\n')
            self.assertEqual({p.name for p in counter.counted_files(root)}, {'application.json','agent.py'})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'tutorial'
        self.project.mkdir()
        (self.project / 'pyproject.toml').write_text('[project]\nname="fixture"\n')
        (self.project / 'uv.lock').write_text('version = 1\n')

    def install(self, *args, **kwargs):
        env = self.project / '.venv'
        env.mkdir()
        (env / 'installed.py').write_text('original = True\n')
        # An external symlink must not be read or removed at retirement.
        (self.root / 'external').write_text('keep\n')
        (env / 'external').symlink_to(self.root / 'external')

    def start(self):
        with patch.object(workspace, 'run', side_effect=self.install) as run:
            workspace.environment(self.project, 'start', 'experiment-1')
            self.assertEqual(run.call_args.args, ('uv', 'sync', '--locked', '--project', str(self.project)))
            self.assertEqual(run.call_args.kwargs['env']['UV_PROJECT_ENVIRONMENT'], str(self.project / '.venv'))

    def test_retirement_preserves_external_target_and_rebuild_record(self):
        self.start()
        workspace.environment(self.project, 'retire', 'experiment-1', inactive=True)
        self.assertFalse((self.project / '.venv').exists())
        self.assertEqual((self.root / 'external').read_text(), 'keep\n')
        receipt = json.loads((self.project / '.rasa-environment-retired.json').read_text())
        self.assertEqual(receipt['inputs'], workspace.inputs(self.project))

    def test_modified_source_is_retained(self):
        self.start()
        env = self.project / '.venv'
        (env / 'installed.py').write_text('unique_experiment = True\n')
        with self.assertRaises(SystemExit):
            workspace.environment(self.project, 'retire', 'experiment-1', inactive=True)
        self.assertTrue(env.exists())

    def test_owner_and_active_jobs_are_required(self):
        self.start()
        with self.assertRaises(SystemExit):
            workspace.environment(self.project, 'retire', 'other-owner', inactive=True)
        with self.assertRaises(SystemExit):
            workspace.environment(self.project, 'retire', 'experiment-1')
        self.assertTrue((self.project / '.venv').exists())

    def test_worktree_and_archive_exclude_installed_environment(self):
        repo = self.root / 'repo'
        repo.mkdir()
        # Git hooks export repository-local variables. Without clearing them,
        # even `git -C <fixture>` can initialise or commit in the real checkout.
        fixture_env = os.environ.copy()
        local_variables = subprocess.check_output(
            ['git', 'rev-parse', '--local-env-vars'], text=True).splitlines()
        for name in local_variables:
            fixture_env.pop(name, None)
        def git(*args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True,
                                  capture_output=True, env=fixture_env)
        git('init')
        (repo / '.gitignore').write_text('.venv/\nnode_modules/\n')
        (repo / 'source.py').write_text('source = True\n')
        for directory in ('.venv', 'node_modules'):
            (repo / directory).mkdir()
            (repo / directory / 'large-install').write_text('dependency\n')
        git('add', '.')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'fixture')
        script = str(Path(workspace.__file__).absolute())
        checkout = self.root / 'new-worktree'
        subprocess.run(['python3', script, 'worktree', str(checkout), 'fixture-next'], cwd=repo, check=True, capture_output=True, env=fixture_env)
        self.assertFalse((checkout / '.venv').exists())
        self.assertFalse((checkout / 'node_modules').exists())
        archive = self.root / 'source.tar'
        subprocess.run(['python3', script, 'snapshot', str(archive)], cwd=repo, check=True, capture_output=True, env=fixture_env)
        import tarfile
        with tarfile.open(archive) as tar:
            self.assertEqual(set(tar.getnames()), {'.gitignore', 'source.py'})


if __name__ == '__main__':
    unittest.main()
