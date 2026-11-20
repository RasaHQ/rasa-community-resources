"""Real filesystem/process boundaries for repository maintenance entrypoints."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import entrypoints as ep

OID = 'a' * 40
ZERO = '0' * 40
ROOT = Path(__file__).resolve().parent.parent


def update(local='refs/heads/work', remote='refs/heads/work', oid=OID):
    return f'{local} {oid} {remote} {ZERO}\n'


class EntryPointsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'examples/demo'
        self.project.mkdir(parents=True)
        for name, text in {'pyproject.toml': '[project]\nname="demo"\nrequires-python=">=3.11"\n',
                           'uv.lock': 'version = 1\n', 'Makefile': 'run:\n\t@true\n'}.items():
            (self.project / name).write_text(text)
        self.env = {'PROJECT': 'examples/demo', 'EXPERIMENT': 'test-owner'}

    def test_all_protected_destinations_are_checked_before_host_or_verification(self):
        for dest in ('refs/heads/main', 'refs/heads/master'):
            for oid in (OID, ZERO):
                with self.subTest(dest=dest, oid=oid), patch.object(ep, 'current_mode') as host, patch.object(ep.subprocess, 'run') as run:
                    with self.assertRaisesRegex(ep.EntrypointError, 'Direct main/master'):
                        ep.push(self.root, update() + update(remote=dest, oid=oid))
                    host.assert_not_called()
                    run.assert_not_called()

    def test_malformed_updates_refuse_before_host_check(self):
        for raw in ('bad\n', update() + 'refs/heads/x bad refs/heads/y bad\n'):
            with patch.object(ep, 'current_mode') as host, self.assertRaises(ep.EntrypointError):
                ep.push(self.root, raw)
            host.assert_not_called()

    def test_source_only_work_push_runs_no_application_process(self):
        with patch.object(ep, 'current_mode', return_value='source'), patch.object(ep, 'capture', return_value='refs/heads/work'), patch.object(ep.subprocess, 'run') as run:
            self.assertEqual(ep.push(self.root, update()), 0)
            run.assert_not_called()

    def test_source_only_refuses_tags_releases_and_deletions(self):
        for raw in (update(remote='refs/tags/v1'), update(remote='refs/heads/release/v1'), update(oid=ZERO)):
            with patch.object(ep, 'current_mode', return_value='source'), patch.object(ep, 'capture', return_value='refs/heads/work'), patch.object(ep.subprocess, 'run') as run:
                with self.assertRaises(ep.EntrypointError):
                    ep.push(self.root, raw)
                run.assert_not_called()

    def test_unidentified_host_refuses(self):
        with patch.object(ep, 'current_mode', return_value='refuse'), patch.object(ep.subprocess, 'run') as run:
            with self.assertRaises(ep.EntrypointError):
                ep.push(self.root, update())
            run.assert_not_called()
        self.assertEqual(ep.host_mode('Darwin', ''), 'refuse')
        self.assertEqual(ep.host_mode('Darwin', 'Mac mini'), 'source')
        self.assertEqual(ep.host_mode('Linux', ''), 'full')

    def test_full_push_propagates_real_child_failure(self):
        fakebin = self.root / 'bin'
        fakebin.mkdir()
        marker = self.root / 'gate-was-called'
        make = fakebin / 'make'
        make.write_text('#!/bin/sh\nprintf "%s" "$*" > "$GATE_MARKER"\nexit 7\n')
        make.chmod(0o755)
        with patch.object(ep, 'current_mode', return_value='full'), patch.dict(os.environ, {'PATH': str(fakebin), 'GATE_MARKER': str(marker)}):
            self.assertEqual(ep.push(self.root, update()), 7)
        self.assertEqual(marker.read_text(), '--no-print-directory verify')

    def test_real_hook_refuses_mixed_destination_before_make(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.githooks').mkdir()
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / '.githooks/pre-push', self.root / '.githooks/pre-push')
        shutil.copyfile(ROOT / 'scripts/entrypoints.py', self.root / 'scripts/entrypoints.py')
        result = subprocess.run(['sh', '.githooks/pre-push'], cwd=self.root,
                                input=update() + update(remote='refs/heads/main'),
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Direct main/master', result.stderr)
        self.assertNotIn('verify', result.stdout)

    def test_selection_refuses_outside_and_symlinked_inputs(self):
        for project in ('../outside', str(self.project), 'scripts', 'examples/missing'):
            with self.subTest(project=project), self.assertRaises(ep.EntrypointError):
                ep.selected_project(self.root, {**self.env, 'PROJECT': project})
        (self.project / 'uv.lock').unlink()
        (self.project / 'uv.lock').symlink_to(self.project / 'pyproject.toml')
        with self.assertRaises(ep.EntrypointError):
            ep.selected_project(self.root, self.env)

    def test_selected_setup_invokes_only_selected_workspace(self):
        with patch.object(ep, 'require_build_host'), patch.object(ep, 'install_hooks') as hooks, patch.object(ep.subprocess, 'run') as run:
            ep.operate(self.root, 'setup', self.env)
            run.assert_called_once()
            args = run.call_args.args[0]
            self.assertEqual(args[2:], ['scripts/workspace.py', 'start', str(self.project), '--owner', 'test-owner'])
            hooks.assert_called_once_with(self.root)

    def test_setup_refusal_has_no_side_effects(self):
        for env in ({}, {'PROJECT': '../outside', 'EXPERIMENT': 'test'}):
            with patch.object(ep, 'require_build_host'), patch.object(ep, 'install_hooks') as hooks, patch.object(ep.subprocess, 'run') as run:
                with self.assertRaises(ep.EntrypointError):
                    ep.operate(self.root, 'setup', env)
                hooks.assert_not_called()
                run.assert_not_called()
        with patch.object(ep, 'current_mode', return_value='source'), patch.object(ep.subprocess, 'run') as run:
            with self.assertRaises(ep.EntrypointError):
                ep.operate(self.root, 'setup', self.env)
            run.assert_not_called()

    def test_clean_requires_inactive_before_any_child(self):
        with patch.object(ep, 'require_build_host'), patch.object(ep.subprocess, 'run') as run:
            with self.assertRaisesRegex(ep.EntrypointError, 'INACTIVE=1'):
                ep.operate(self.root, 'clean', self.env)
            run.assert_not_called()

    def test_run_requires_matching_owner_and_locked_inputs(self):
        marker = self.project / '.venv/.rasa-workspace.json'
        marker.parent.mkdir()
        record = {'owner': 'other-owner', 'project': str(self.project), 'inputs': {n: hashlib.sha256((self.project / n).read_bytes()).hexdigest() for n in ('pyproject.toml', 'uv.lock')}}
        marker.write_text(json.dumps(record))
        with patch.object(ep, 'require_build_host'), patch.object(ep.subprocess, 'run') as run:
            with self.assertRaises(ep.EntrypointError):
                ep.operate(self.root, 'run', self.env)
            run.assert_not_called()

    def test_run_overrides_inherited_environment_with_selected_managed_path(self):
        marker = self.project / '.venv/.rasa-workspace.json'
        marker.parent.mkdir()
        record = {'owner': 'test-owner', 'project': str(self.project), 'inputs': {n: hashlib.sha256((self.project / n).read_bytes()).hexdigest() for n in ('pyproject.toml', 'uv.lock')}}
        marker.write_text(json.dumps(record))
        with patch.object(ep, 'require_build_host'), patch.object(ep.subprocess, 'run') as run:
            run.return_value.returncode = 9
            self.assertEqual(ep.operate(self.root, 'run', {**self.env, 'UV_PROJECT_ENVIRONMENT': '/outside'}), 9)
            self.assertEqual(run.call_args.kwargs['env']['UV_PROJECT_ENVIRONMENT'], str(self.project / '.venv'))

    def test_doctor_never_reads_dotenv_or_prints_values_or_writes(self):
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/maintenance-toolchain.json', self.root / 'scripts/maintenance-toolchain.json')
        (self.root / 'RASA_PRO_VERSION').write_text('example-pin\n')
        (self.root / '.env').write_text('RASA_LICENSE=PRIVATE_SENTINEL\n$(shell touch should-not-exist)\n')
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        output = io.StringIO()
        original = Path.read_text
        def guarded_read(path, *args, **kwargs):
            self.assertNotEqual(path.name, '.env')
            return original(path, *args, **kwargs)
        with patch.object(ep, 'capture', return_value=''), patch.object(ep, 'hook_current', return_value=False), patch.object(Path, 'read_text', guarded_read), patch.object(ep.urllib.request, 'urlopen') as network, contextlib.redirect_stdout(output):
            result = ep.doctor(self.root, True, {'RASA_LICENSE': 'PRIVATE_SENTINEL'})
        self.assertEqual(result, 1)
        self.assertNotIn('PRIVATE_SENTINEL', output.getvalue())
        self.assertIn('RASA_LICENSE: set', output.getvalue())
        self.assertIn('connectivity is unverified', output.getvalue())
        network.assert_not_called()
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_help_needs_no_python_catalog_or_dotenv(self):
        shutil.copyfile(ROOT / 'Makefile', self.root / 'Makefile')
        (self.root / '.env').write_text('BAD=$(shell touch DOTENV_WAS_EVALUATED)\n')
        for target in ('help', 'help-all'):
            result = subprocess.run(['make', '--no-print-directory', target, 'PYTHON=false'], cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('No projects discovered', result.stdout)
        self.assertFalse((self.root / 'DOTENV_WAS_EVALUATED').exists())

    def test_worktree_hook_install_is_scoped_and_detects_stale_source(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.githooks').mkdir()
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / '.githooks/pre-push', self.root / '.githooks/pre-push')
        shutil.copyfile(ROOT / 'scripts/entrypoints.py', self.root / 'scripts/entrypoints.py')
        (self.root / '.githooks/pre-push').chmod(0o755)
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True)
        subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Fixture'], cwd=self.root, check=True)
        ep.install_hooks(self.root)
        self.assertTrue(ep.hook_current(self.root))
        sibling = self.root.parent / (self.root.name + '-sibling')
        subprocess.run(['git', 'worktree', 'add', '-qb', 'sibling', str(sibling)], cwd=self.root, check=True, capture_output=True)
        self.addCleanup(shutil.rmtree, sibling, True)
        self.assertFalse(ep.hook_current(sibling))
        with (self.root / '.githooks/pre-push').open('a') as stream:
            stream.write('# changed\n')
        self.assertFalse(ep.hook_current(self.root))


if __name__ == '__main__':
    unittest.main()
