"""Refusal tests for the no-network wrapper behind the protected gate.

A wrapper that does not exist, does not run Python, or does not block a connection must never
produce ACCEPT. Wrappers come from the system PATH. These tests do not defend against a hostile
administrator replacing system tools.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import factory_gate


class Refusals(unittest.TestCase):
    def setUp(self):
        self.iso = factory_gate._isolation()
        self.pack = factory_gate._pack()
        self.tmp = Path(tempfile.mkdtemp(prefix='isolation-refusal-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def script(self, name, body):
        path = self.tmp / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return str(path)

    def fake_path(self):
        """A PATH holding only pass-through look-alikes of every wrapper the module can try."""
        bin_dir = self.tmp / 'bin'
        bin_dir.mkdir()
        for name in ('sandbox-exec', 'unshare', 'bwrap', 'sudo', 'setpriv'):
            (bin_dir / name).write_text('#!/bin/sh\nexec "$@"\n')
            (bin_dir / name).chmod(0o755)
        return str(bin_dir)

    def test_no_wrapper_is_not_proven(self):
        self.assertFalse(self.iso.blocks([]))

    def test_a_pass_through_wrapper_is_not_proven(self):
        self.assertFalse(self.iso.blocks([self.script('pass', '#!/bin/sh\nexec "$@"\n')]))

    def test_a_wrapper_that_exits_zero_without_running_python_is_not_proven(self):
        self.assertFalse(self.iso.blocks([self.script('quiet', '#!/bin/sh\nexit 0\n')]))

    def test_a_wrapper_that_cannot_start_is_not_proven(self):
        self.assertFalse(self.iso.blocks([str(self.tmp / 'missing-wrapper')]))

    def test_the_gate_reports_not_ready_when_nothing_is_proven(self):
        class Nothing:
            @staticmethod
            def first_blocking():
                return None
        for kind in ('good', 'ignores-limit'):
            with patch.object(factory_gate, '_isolation', return_value=Nothing):
                result = factory_gate.run_factory(kind)
            self.assertEqual(result['verdict'], 'NOT_READY', result)
            self.assertIn('proven', result['reason'])

    def test_run_a6_refuses_when_only_pass_through_look_alikes_exist(self):
        env = {'PATH': self.fake_path(), 'PYTHONDONTWRITEBYTECODE': '1'}
        done = subprocess.run([sys.executable, '-I', str(self.pack / 'run_a6.py'),
                               str(self.pack / 'tasks/b-limit-currencies.json'), 'baseline'],
                              capture_output=True, text=True, timeout=120, env=env, cwd=self.pack)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn('could not run', done.stdout)
        self.assertNotIn('ACCEPT', done.stdout)

    SENTINEL_CODE = "\nfrom pathlib import Path as _P\n_P(__file__).with_name('SENTINEL').write_text('ran')\n"

    def tampered_copy(self):
        copy = self.tmp / 'ch06'
        shutil.copytree(self.pack, copy, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        with (copy / 'isolation.py').open('a') as handle:
            handle.write(self.SENTINEL_CODE)
        return copy

    def test_the_sentinel_proves_an_executed_isolation_module_would_be_seen(self):
        copy = self.tampered_copy()
        spec = importlib.util.spec_from_file_location('isolation_control', copy / 'isolation.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue((copy / 'SENTINEL').exists())

    def test_run_a6_refuses_an_edited_isolation_module_without_executing_it(self):
        copy = self.tampered_copy()
        done = subprocess.run([sys.executable, '-I', str(copy / 'run_a6.py'),
                               str(copy / 'tasks/b-limit-currencies.json'), 'baseline'],
                              capture_output=True, text=True, timeout=120, cwd=copy,
                              env={'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn('does not match its pin', done.stdout)
        self.assertNotIn('ACCEPT', done.stdout)
        self.assertFalse((copy / 'SENTINEL').exists(), 'isolation.py ran before its pin was checked')

    def test_the_gate_refuses_an_edited_isolation_module_without_executing_it(self):
        copy = self.tampered_copy()
        with patch.object(factory_gate, '_pack', return_value=copy):
            result = factory_gate.run_factory('good')
        self.assertEqual(result['verdict'], 'NOT_READY', result)
        self.assertFalse((copy / 'SENTINEL').exists(), 'isolation.py ran before its pin was checked')

    def test_live_good_stays_not_ready_on_linux_before_any_funded_run(self):
        fake_sys = types.SimpleNamespace(platform='linux', executable=sys.executable)
        with patch.object(factory_gate, 'sys', fake_sys), \
                patch.object(factory_gate, '_live', side_effect=AssertionError('a funded run was started')):
            result = factory_gate.run_factory('good', mode='LIVE')
        self.assertEqual(result['verdict'], 'NOT_READY', result)
        self.assertIn('not ported', result['reason'])

    def test_a_proven_wrapper_exists_here_or_the_gate_says_so(self):
        prefix = self.iso.first_blocking()
        if prefix is None:
            self.assertEqual(factory_gate.run_factory('good')['verdict'], 'NOT_READY')
        else:
            self.assertTrue(self.iso.blocks(prefix))


if __name__ == '__main__':
    unittest.main()
