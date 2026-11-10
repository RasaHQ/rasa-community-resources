"""Make target controls, synthetic credentials and owned local processes only.

"""
from contextlib import chdir, redirect_stdout, redirect_stderr
import io
import errno
import socket
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import demo_launcher as demo
import demo_make as commands


class FriendlyMake(unittest.TestCase):
    def setUp(self):
        (SOURCE / '.demo-cache').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=SOURCE / '.demo-cache')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project, self.worker = self.root / 'project', self.root / 'worker'
        self.project.mkdir()
        self.worker.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (self.root / '.gitignore').write_text('.env\n')
        self.template = ''.join(name + '=\n' for name in sorted(demo.PARTICIPANT_KEYS))
        (self.root / '.env.example').write_text(self.template)
        for name, value in [('ROOT', self.root), ('PROJECT', self.project), ('WORKER', self.worker)]:
            item = patch.object(demo, name, value)
            item.start()
            self.addCleanup(item.stop)

    def output(self, target):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            commands.perform(target)
        return output.getvalue()

    def test_default_make_and_help_list_all_targets_in_order_and_missing_env_tip(self):
        # Real make dispatches every declared target to the launcher interface.
        shutil.copyfile(SOURCE / 'Makefile', self.root / 'Makefile')
        executable = self.root / 'demo'
        executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        executable.chmod(0o755)
        for target in commands.PURPOSES:
            result = subprocess.run(['make', '--no-print-directory', target], cwd=self.root,
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.splitlines(), ['make-target', target])
        result = subprocess.run(['make', '--no-print-directory'], cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.stdout.splitlines(), ['make-target', 'help'])
        output = self.output('help')
        offsets = [output.index('make ' + name + ':') for name in commands.PURPOSES]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn('Run make env first', output)

    def test_env_creates_private_template_never_overwrites_or_echoes_existing_values(self):
        output = self.output('env')
        path = self.root / '.env'
        self.assertEqual(path.read_text(), self.template)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        for name in commands.SOURCES:
            self.assertIn(name, output)
        synthetic = 'make-env-only-fixture-never-echo-321'
        content = 'RASA_LICENSE=' + synthetic + '\n'
        path.write_text(content)
        path.chmod(0o644)
        output = self.output('env')
        self.assertEqual(path.read_text(), content)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(synthetic, output)

    def test_env_refuses_symlink_and_nonempty_or_missing_template(self):
        path = self.root / '.env'
        path.symlink_to(self.root / '.env.example')
        with self.assertRaises(demo.DemoError):
            commands.perform('env')
        path.unlink()
        (self.root / '.env.example').write_text('RASA_LICENSE=template-must-be-empty\n')
        with self.assertRaises(demo.DemoError):
            commands.perform('env')
        self.assertFalse(path.exists())
        (self.root / '.env.example').unlink()
        with self.assertRaises(demo.DemoError):
            commands.perform('env')

    def test_operating_targets_require_env_before_any_child(self):
        for target in ('doctor', 'run', 'run-scripted'):
            with self.subTest(target=target), patch.object(demo.Children, 'start') as start:
                with self.assertRaisesRegex(demo.DemoError, 'Run make env first'):
                    self.output(target)
                start.assert_not_called()

    def test_setup_and_run_targets_use_actual_launcher_actions(self):
        self.output('env')
        with patch.object(demo, 'setup') as setup:
            self.output('setup')
            setup.assert_called_once_with()
        for target, scripted in [('run', False), ('run-scripted', True)]:
            with patch.object(demo, 'run_demo') as run:
                output = self.output(target)
                run.assert_called_once_with(scripted=scripted, host='127.0.0.1')
                self.assertIn('http://127.0.0.1:8942/', output)

    def test_make_run_uses_runtime_viewer_address_and_prints_matching_page(self):
        self.output('env')
        with patch.dict(os.environ, {'BRIEFING_VIEWER_HOST': '100.64.0.10'}), \
                patch.object(demo, 'run_demo') as run:
            output = self.output('run')
            run.assert_called_once_with(scripted=False, host='100.64.0.10')
            self.assertIn('http://100.64.0.10:8942/', output)

    def test_make_setup_and_test_never_read_participant_values(self):
        # Setup and tests also work before make env.
        with patch.object(demo, 'setup') as setup:
            self.output('setup')
            setup.assert_called_once_with()
        with patch.object(commands, 'project_python', return_value=Path(sys.executable)), patch.object(demo, 'completed'):
            self.output('test')
        self.output('env')
        # A synthetic invalid assignment proves these paths do not parse values.
        (self.root / '.env').write_text('UNKNOWN=synthetic-not-for-builds\n')
        with patch.object(demo, 'participant_environment', side_effect=AssertionError('must not load values')), \
                patch.object(demo, 'setup') as setup:
            self.output('setup')
            setup.assert_called_once_with()
        with patch.object(demo, 'participant_environment', side_effect=AssertionError('must not load values')), \
                patch.object(commands, 'project_python', return_value=Path(sys.executable)), \
                patch.object(demo, 'completed') as completed:
            self.output('test')
            self.assertTrue(demo.PARTICIPANT_KEYS.isdisjoint(completed.call_args.kwargs['env']))

    def test_doctor_and_test_use_installed_interpreter_and_test_strips_keys(self):
        self.output('env')
        (self.root / '.env').write_text('RASA_LICENSE=synthetic-only\n')
        interpreter = self.project / '.venv' / 'bin' / 'python'
        with patch.object(commands, 'project_python', return_value=interpreter), \
                patch.object(demo, 'completed') as completed:
            output = self.output('doctor')
            self.assertIn('RASA_LICENSE: SET', output)
            self.assertIn('DEEPGRAM_API_KEY: MISSING', output)
            self.assertNotIn('synthetic-only', output)
            self.assertEqual(completed.call_args.args[1], [str(interpreter), str(self.root / 'class_doctor.py')])
            self.assertEqual(completed.call_args.kwargs['env']['RASA_LICENSE'], 'synthetic-only')
            self.output('test')
            self.assertIn('unittest', completed.call_args.args[1])
            self.assertTrue(demo.PARTICIPANT_KEYS.isdisjoint(completed.call_args.kwargs['env']))

    def test_missing_uv_and_python_have_plain_fixes(self):
        self.output('env')
        with patch.object(demo.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(demo.DemoError, 'Install uv'):
                commands.perform('setup')
        with self.assertRaisesRegex(demo.DemoError, 'Python 3.12'):
            commands.project_python()
        interpreter = demo.python_at(self.project)
        interpreter.parent.mkdir(parents=True)
        interpreter.touch()
        with patch.object(commands.subprocess, 'run') as run:
            run.return_value.returncode = 1
            with self.assertRaisesRegex(demo.DemoError, 'Install Python 3.12'):
                commands.project_python()

    def test_clean_only_owned_environments_preserves_env_and_other_files(self):
        self.output('env')
        keep = self.root / 'leave-this-file'
        keep.write_text('ordinary data')
        (self.root / '.demo-cache').mkdir(exist_ok=True)
        (self.root / '.demo-cache' / 'cache-item').write_text('scratch data')
        for directory in (self.worker, self.project):
            (directory / '.venv').mkdir()
            commands.mark_environment(directory)
        self.output('clean')
        self.assertFalse((self.worker / '.venv').exists())
        self.assertFalse((self.project / '.venv').exists())
        self.assertTrue((self.root / '.env').is_file())
        self.assertTrue(keep.is_file())
        self.assertFalse((self.root / '.demo-cache').exists())

    def test_clean_refuses_unmarked_foreign_symlink_and_running_before_any_delete(self):
        for directory in (self.worker, self.project):
            (directory / '.venv').mkdir()
        commands.mark_environment(self.worker)
        with self.assertRaises(demo.DemoError):
            commands.clean_environments()
        self.assertTrue((self.worker / '.venv').is_dir())
        commands.mark_environment(self.project)
        marker = self.project / '.venv' / '.demo-owner.json'
        marker.write_text(json.dumps({'checkout': 'another-checkout', 'environment': 'another-environment'}))
        with self.assertRaises(demo.DemoError):
            commands.clean_environments()
        self.assertTrue((self.worker / '.venv').is_dir())
        shutil.rmtree(self.project / '.venv')
        (self.project / '.venv').symlink_to(self.worker / '.venv')
        with self.assertRaises(demo.DemoError):
            commands.clean_environments()
        (self.project / '.venv').unlink()
        directory = commands.runtime_directory(self.root)
        (directory / 'control.sock').touch()
        with self.assertRaises(demo.DemoError):
            commands.clean_environments()

    def test_stop_without_control_never_signals_any_process(self):
        with patch.object(commands.os, 'kill') as kill:
            self.assertIn('No demo is running', self.output('stop'))
            kill.assert_not_called()
        directory = commands.runtime_directory(self.root)
        (directory / 'control.sock').touch()
        with self.assertRaises(demo.DemoError), patch.object(commands.os, 'kill') as kill:
            commands.stop_checkout(self.root)
        kill.assert_not_called()

    def test_crashed_private_socket_is_recovered_and_can_restart(self):
        with chdir(self.root):
            path = commands.runtime_directory(self.root) / 'control.sock'
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as crashed:
                crashed.bind(commands.control_address(self.root))
                path.chmod(0o600)
            with patch.object(commands.os, 'kill') as kill:
                self.assertIn('stale control socket', self.output('stop'))
                kill.assert_not_called()
            self.assertFalse(path.exists())
            control = commands.CheckoutControl(self.root)
            control.start()
            control.close()
            self.assertFalse(path.exists())

    def test_timeout_permission_and_changed_socket_never_unlink(self):
        with chdir(self.root):
            path = commands.runtime_directory(self.root) / 'control.sock'
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as crashed:
                crashed.bind(commands.control_address(self.root))
                path.chmod(0o600)
            for error in (TimeoutError(), PermissionError(errno.EACCES, 'denied')):
                with self.subTest(error=type(error).__name__), patch.object(commands.socket, 'socket') as factory:
                    factory.return_value.__enter__.return_value.connect.side_effect = error
                    with self.assertRaises(demo.DemoError):
                        commands.stop_checkout(self.root)
                    self.assertTrue(path.exists())
            def replace_socket(*args):
                path.unlink()
                path.write_text('replacement must survive')
                raise ConnectionRefusedError(errno.ECONNREFUSED, 'refused')
            with patch.object(commands.socket, 'socket') as factory:
                factory.return_value.__enter__.return_value.connect.side_effect = replace_socket
                with self.assertRaises(demo.DemoError):
                    commands.stop_checkout(self.root)
            self.assertEqual(path.read_text(), 'replacement must survive')

    def test_real_stop_contacts_only_own_checkout_socket(self):
        source = str(SOURCE)
        code = ('import sys,time; from pathlib import Path; sys.path.insert(0, ' + repr(source) + '); '
                'from demo_make import CheckoutControl; c=CheckoutControl(Path.cwd()); c.start(); '
                'Path("ready").touch()\n'
                'try: time.sleep(30)\n'
                'except KeyboardInterrupt: pass\n'
                'finally: c.close()\n')
        own = subprocess.Popen([sys.executable, '-c', code], cwd=self.root,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / 'ready').exists() and time.monotonic() < deadline:
                if own.poll() is not None:
                    self.fail('Synthetic checkout control exited before readiness')
                time.sleep(0.05)
            self.assertTrue((self.root / 'ready').exists())
            stop = 'import sys;from pathlib import Path;sys.path.insert(0,' + repr(source) + ');from demo_make import stop_checkout;stop_checkout(Path.cwd())'
            subprocess.run([sys.executable, '-c', stop], cwd=self.root, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            self.assertEqual(own.wait(timeout=5), 0)
            self.assertIsNone(unrelated.poll())
            self.assertFalse((self.root / '.demo-runtime' / 'control.sock').exists())
        finally:
            for process in (own, unrelated):
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
