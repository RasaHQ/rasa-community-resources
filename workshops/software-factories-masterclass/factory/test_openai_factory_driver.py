"""Injected native-boundary and actual filesystem confinement controls.
sow: software-factories-masterclass-SOW-02
"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('openai_factory_driver', HERE / 'agent-runs/drivers/openai_factory_driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class DriverControls(unittest.TestCase):
    def setUp(self):
        cache = HERE / '.driver-test-cache'
        cache.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / 'scratch'
        self.workspace.mkdir()
        self.task = {'id': 'A6-fixture', 'request': 'Add a labelled market card.',
                     'allowed_paths': ['product/market.py', 'product/tests/'],
                     'excluded': 'Do not read or edit protected gates.',
                     'acceptance': {'path': 'acceptance/hidden.py', 'sha256': 'hidden-suite-fingerprint'}}
        (self.workspace / 'product').mkdir()
        (self.workspace / 'product' / 'agent.yml').write_text('agent: {}\n')
        (self.workspace / 'tasks').mkdir()
        visible = {key: self.task[key] for key in ('id', 'request', 'allowed_paths', 'excluded')}
        (self.workspace / 'tasks' / 'A6-fixture.json').write_text(json.dumps(visible))
        (self.workspace / 'AGENTS.md').write_text('Only allowed product paths. No protected suite.')
        (self.workspace / '.scratch.json').write_text('{}')
        self.task_path = self.root / 'A6-fixture.json'
        self.task_path.write_text(json.dumps(self.task))
        self.outside = self.root / 'protected.py'
        self.outside.write_text('holdout-must-never-be-visible')

    def files(self):
        result = driver.ConfinedFiles(self.workspace, self.task)
        self.addCleanup(result.close)
        return result

    def test_allowed_read_write_and_visible_task_without_holdout(self):
        files = self.files()
        self.assertTrue(files.read_file({'path': 'AGENTS.md'})['ok'])
        self.assertTrue(files.write_file({'path': 'product/market.py', 'text': 'daily_reference = True\n'})['ok'])
        self.assertEqual((self.workspace / 'product/market.py').read_text(), 'daily_reference = True\n')
        listing = files.list_files({})['files']
        self.assertNotIn('.scratch.json', listing)
        self.assertNotIn('protected.py', listing)
        visible = files.read_file({'path': 'tasks/A6-fixture.json'})['text']
        self.assertNotIn('hidden-suite-fingerprint', visible)

    def test_traversal_prefix_confusion_protected_paths_and_dotfiles_refused(self):
        files = self.files()
        for name in ('../protected.py', str(self.outside), 'product/../protected.py',
                     'product/.env', 'acceptance/hidden.py', 'product/protected/hidden.py',
                     'product/market.py.evil', 'product/tests-not-allowed/fake.py'):
            with self.subTest(path=name):
                self.assertFalse(files.write_file({'path': name, 'text': 'no'})['ok'])
        for name in ('../protected.py', str(self.outside), '.scratch.json', 'acceptance/hidden.py', 'product/.env'):
            self.assertFalse(files.read_file({'path': name})['ok'])
        self.assertEqual(self.outside.read_text(), 'holdout-must-never-be-visible')

    def test_links_fifo_directories_and_hardlinks_do_not_escape_or_block(self):
        files = self.files()
        path = self.workspace / 'product/market.py'
        path.symlink_to(self.outside)
        self.assertFalse(files.read_file({'path': 'product/market.py'})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'no'})['ok'])
        path.unlink()
        os.link(self.outside, path)
        self.assertFalse(files.read_file({'path': 'product/market.py'})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'no'})['ok'])
        path.unlink()
        os.mkfifo(path)
        self.assertFalse(files.read_file({'path': 'product/market.py'})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'no'})['ok'])
        path.unlink()
        directory = self.workspace / 'product/tests'
        directory.symlink_to(self.root)
        self.assertFalse(files.write_file({'path': 'product/tests/protected.py', 'text': 'no'})['ok'])
        self.assertEqual(self.outside.read_text(), 'holdout-must-never-be-visible')

    def test_file_and_cumulative_limits_and_host_credentials(self):
        files = self.files()
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'x' * 65537})['ok'])
        synthetic = 'native-builder-fixture-secret-123456789'
        with patch.dict(os.environ, {'OPENAI_API_KEY': synthetic}):
            self.assertFalse(files.write_file({'path': 'product/market.py', 'text': synthetic})['ok'])
        for _ in range(8):
            self.assertTrue(files.write_file({'path': 'product/market.py', 'text': 'x' * 65536})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'x'})['ok'])

    def test_closed_tools_refuse_all_late_callbacks(self):
        files = self.files()
        files.close()
        self.assertFalse(files.read_file({'path': 'AGENTS.md'})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'late mutation'})['ok'])
        self.assertFalse(files.list_files({})['ok'])
        self.assertFalse((self.workspace / 'product/market.py').exists())

    def test_scratch_preflight_rejects_repo_protected_and_unsafe_task(self):
        driver.validate_scratch(self.workspace, self.task)
        (self.workspace / 'acceptance').mkdir()
        with self.assertRaises(ValueError):
            driver.validate_scratch(self.workspace, self.task)
        (self.workspace / 'acceptance').rmdir()
        unsafe = {**self.task, 'allowed_paths': ['../acceptance/']}
        with self.assertRaises(ValueError):
            driver.ConfinedFiles(self.workspace, unsafe)
        (self.workspace / '.scratch.json').unlink()
        with self.assertRaises(ValueError):
            driver.validate_scratch(self.workspace, self.task)

    def test_one_bounded_native_session_exposes_only_three_file_tools(self):
        calls = []
        events = []
        def invoke(client, **kwargs):
            calls.append(kwargs)
            self.assertEqual(set(kwargs['handlers']), {'list_files', 'read_file', 'write_file'})
            self.assertNotIn('acceptance', json.loads(kwargs['text']))
            self.assertNotIn('hidden-suite-fingerprint', kwargs['text'])
            self.assertTrue(kwargs['handlers']['write_file']({'path': 'product/market.py', 'text': 'REFERENCE = True\n'})['ok'])
            return SimpleNamespace(ok=True)
        result = driver.native_builder(object(), task=self.task, workspace=self.workspace,
                                       event=lambda **values: events.append(values), model='injected-no-network',
                                       invoke=invoke, tool_factory=lambda name, description, schema: {'name': name, 'parameters': schema})
        self.assertTrue(result.ok)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['max_calls'], 30)
        self.assertNotIn('spend_limit_cents', calls[0])
        self.assertNotIn('spend_control', calls[0])
        self.assertEqual(calls[0]['deadline_seconds'], 120)
        self.assertEqual(calls[0]['environment'], {'type': 'none'})
        self.assertEqual(calls[0]['agent']['service_tier'], 'default')
        self.assertEqual([e['action'] for e in events], ['session_started', 'write_file', 'session_finished'])
        self.assertNotIn('REFERENCE = True', json.dumps(events))

    def test_local_estimate_is_checked_without_sending_any_provider_cap(self):
        calls = []
        def invoke(client, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(ok=True)
        options = dict(client=object(), task=self.task, workspace=self.workspace,
                       event=lambda **values: None, model='scripted', invoke=invoke,
                       tool_factory=lambda *args: {})
        for limit, estimate in ((None, 1), (200, None), (29, 1), (True, 1), (200, False)):
            with self.subTest(limit=limit, estimate=estimate), self.assertRaises(ValueError):
                driver.native_builder(**options, spend_limit_cents=limit, estimated_cents_per_call=estimate)
        self.assertEqual(calls, [])
        driver.native_builder(**options, spend_limit_cents=30, estimated_cents_per_call=1)
        driver.native_builder(**options)
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertNotIn('spend_limit_cents', call)
            self.assertNotIn('spend_control', call)

    def test_native_prompt_exposes_public_limit_without_verifier_metadata(self):
        task = {**self.task, 'limit': 2}
        def invoke(client, **kwargs):
            visible = json.loads(kwargs['text'])
            self.assertEqual(visible['limit'], 2)
            self.assertNotIn('acceptance', visible)
            return SimpleNamespace(ok=True)
        driver.native_builder(object(), task=task, workspace=self.workspace,
                              event=lambda **values: None, model='scripted', invoke=invoke,
                              tool_factory=lambda *args: {})

    def test_usage_receipt_keeps_only_numeric_metrics_without_session_or_text(self):
        requests = []
        session = SimpleNamespace(usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120,
            input_tokens_details=SimpleNamespace(cached_tokens=10), output_tokens_details=SimpleNamespace(reasoning_tokens=5)),
            agent=SimpleNamespace(service_tier='default'), spend_control=SimpleNamespace(consumed=1),
            raw_text='not-public-model-text')
        def retrieve(session_id, **kwargs):
            requests.append((session_id, kwargs))
            return session
        client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=SimpleNamespace(retrieve=retrieve))))
        receipt = driver.record_usage(client, SimpleNamespace(session_id='private-session-id'), self.root, mode='LIVE_NATIVE')
        self.assertEqual(receipt['status'], 'RECORDED_BEST_EFFORT')
        self.assertEqual(receipt['reasoning_output_tokens'], 5)
        self.assertEqual(requests, [('private-session-id', {'timeout': 20})])
        stored = (self.root / 'usage.json').read_text()
        self.assertNotIn('private-session-id', stored)
        self.assertNotIn('not-public-model-text', stored)
        self.assertIsNone(receipt['actual_billed_cost_cents'])

    def test_scripted_usage_never_reads_provider_and_invalid_counters_are_not_invented(self):
        from unittest.mock import Mock
        client = Mock()
        receipt = driver.record_usage(client, SimpleNamespace(session_id='scripted'), self.root, mode='SCRIPTED')
        client.beta.agents.sessions.retrieve.assert_not_called()
        self.assertEqual(receipt['provider_calls'], 0)
        session = SimpleNamespace(usage=SimpleNamespace(input_tokens=True, output_tokens='20', total_tokens=None))
        client.beta.agents.sessions.retrieve.return_value = session
        receipt = driver.record_usage(client, SimpleNamespace(session_id='owned'), self.root, mode='LIVE_NATIVE')
        self.assertEqual(receipt['status'], 'USAGE_NOT_AVAILABLE')
        self.assertIsNone(receipt['input_tokens'])
        self.assertIsNone(receipt['output_tokens'])

    def test_usage_permission_refusal_keeps_code_not_exception_text(self):
        class Refusal(Exception):
            status_code = 403
            code = 'insufficient_permissions'
        def retrieve(*args, **kwargs):
            raise Refusal('private-provider-body-not-recorded')
        client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(sessions=SimpleNamespace(retrieve=retrieve))))
        receipt = driver.record_usage(client, SimpleNamespace(session_id='owned'), self.root, mode='LIVE_NATIVE')
        self.assertEqual(receipt['provider_detail'], 'http_403 code=insufficient_permissions')
        self.assertNotIn('private-provider-body', (self.root / 'usage.json').read_text())

    def test_missing_sandbox_stops_before_any_native_request(self):
        from unittest.mock import Mock
        run = self.root / 'no-sandbox'
        hook = Mock()
        factory = SimpleNamespace(sandbox_unavailable=lambda path: True)
        with patch.object(driver, 'module', return_value=factory), patch.object(driver, 'native_builder') as native:
            code = driver.execute(self.task_path, self.workspace, run, client=object(), model='never-called',
                                  integration_hook=hook)
        self.assertEqual(code, 2)
        native.assert_not_called()
        hook.assert_not_called()
        self.assertEqual(json.loads((run / 'console.json').read_text())['state'], 'NOT_READY')
        self.assertFalse((run / 'verification').exists())

    def test_noncompleted_session_never_collects_or_accepts_partial_edits(self):
        for status in ('incomplete', 'failed', 'cancelled', None, 'completed'):
            with self.subTest(status=status):
                run = self.root / ('stopped-' + str(status))
                factory = SimpleNamespace(prepare=lambda path: ('injected', []), sandbox_unavailable=lambda path: False)
                with patch.object(driver, 'module', return_value=factory) as load, \
                        patch.object(driver, 'native_builder', return_value=SimpleNamespace(ok=False, status=status)):
                    code = driver.execute(self.task_path, self.workspace, run, client=object(), model='injected')
                self.assertEqual(code, 2)
                self.assertEqual(load.call_count, 1)  # environment preflight only
                self.assertEqual(json.loads((run / 'console.json').read_text())['state'], 'BUILDER_INCOMPLETE')
                self.assertFalse((run / 'candidate').exists())
                self.assertFalse((run / 'verification').exists())

    def test_host_reuses_collect_factory_and_preserves_each_exit_code(self):
        for code in range(5):
            run = self.root / ('run-' + str(code))
            called = []
            def collect(workspace, candidate, review, **kwargs):
                called.append(('collect', Path(workspace)))
                Path(candidate).mkdir()
                Path(review).mkdir()
                return 0
            def factory(task, candidate, verification, **kwargs):
                called.append(('factory', Path(task)))
                Path(verification).mkdir()
                (Path(verification) / 'decision.json').write_text(json.dumps({'decision': 'ACCEPT' if code == 0 else 'REJECT'}))
                return code
            modules = {'collect': SimpleNamespace(main=collect), 'factory': SimpleNamespace(main=factory, prepare=lambda path: ('injected', []), sandbox_unavailable=lambda path: False)}
            with patch.object(driver, 'module', side_effect=lambda name: modules[name]), \
                    patch.object(driver, 'native_builder', return_value=SimpleNamespace(ok=True, status='completed')):
                result = driver.execute(self.task_path, self.workspace, run, client=object(), model='injected')
            self.assertEqual(result, code)
            self.assertEqual([name for name, _ in called], ['collect', 'factory'])
            self.assertTrue((run / 'console.json').is_file())
            self.assertEqual(json.loads((run / 'integration.json').read_text())['status'], 'NOT_RECORDED')
        with self.assertRaises(ValueError):
            driver.execute(self.task_path, self.workspace, self.workspace / 'evidence', client=object(), model='injected')

    def integration_run(self, name, *, hook=None, code=0, decision=None, status='completed', ok=True,
                        read_integration=True):
        """Inject the gate boundary, retaining real candidate bytes/digest custody."""
        directory = self.root / name
        digest_tree = driver.module('factory').digest_tree

        def collect(workspace, candidate, review, **kwargs):
            (Path(candidate) / 'product').mkdir(parents=True)
            (Path(candidate) / 'product/market.py').write_text('market = "checked proposal"\n')
            Path(review).mkdir()
            return 0

        def gate(task, candidate, verification, **kwargs):
            Path(verification).mkdir()
            record = {'decision': 'ACCEPT' if code == 0 else 'REJECT',
                      'candidate_digest': digest_tree(candidate)}
            record.update(decision or {})
            (Path(verification) / 'decision.json').write_text(json.dumps(record))
            return code

        factory = SimpleNamespace(main=gate, digest_tree=digest_tree,
                                  prepare=lambda path: ('injected', []), sandbox_unavailable=lambda path: False)
        modules = {'collect': SimpleNamespace(main=collect), 'factory': factory}
        with patch.object(driver, 'module', side_effect=lambda name: modules[name]), \
                patch.object(driver, 'native_builder', return_value=SimpleNamespace(ok=ok, status=status)):
            result = driver.execute(self.task_path, self.workspace, directory, client=object(), model='injected',
                                    mode='SCRIPTED', integration_hook=hook)
        record = json.loads((directory / 'integration.json').read_text()) if read_integration else None
        return result, directory, record

    @staticmethod
    def owner_record(directory):
        digest = json.loads((directory / 'verification/decision.json').read_text())['candidate_digest']
        return {'schema': 'rasa.factory-integration/v1', 'status': 'APPLIED_RESTARTED',
                'candidate_digest': digest, 'baseline_head': 'a' * 40, 'integrated_head': 'b' * 40,
                'receipt_ref': 'receipts/controlled-owner-http.json', 'reason_code': 'owner_recorded'}

    def test_integration_absent_hook_stays_unrecorded_and_noncallable_is_not_a_command(self):
        result, _, record = self.integration_run('no-hook')
        self.assertEqual(result, 0)
        self.assertEqual(record['status'], 'NOT_RECORDED')
        target = self.root / 'no-import'
        with self.assertRaisesRegex(ValueError, 'programmatic_integration_callable_required'):
            driver.execute(self.task_path, self.workspace, target, client=object(), model='injected',
                           integration_hook='builder-selected-command-or-path')
        self.assertFalse(target.exists())

    def test_integration_never_invoked_on_nonaccept_or_native_failure(self):
        from unittest.mock import Mock
        for code in (1, 2, 3, 4):
            hook = Mock()
            result, _, record = self.integration_run('gate-' + str(code), hook=hook, code=code)
            hook.assert_not_called()
            self.assertEqual(result, code)
            self.assertEqual(record['status'], 'NOT_RECORDED')
        for status, ok in [('failed', False), ('incomplete', False), ('cancelled', False), ('completed', False)]:
            hook = Mock()
            result, _, record = self.integration_run('native-' + status, hook=hook, status=status, ok=ok)
            hook.assert_not_called()
            self.assertEqual(result, 2)
            self.assertEqual(record['status'], 'NOT_RECORDED')

    def test_integration_once_with_resolved_run_path_and_exact_owner_record(self):
        calls = []
        def hook(directory):
            calls.append(directory)
            return self.owner_record(directory)
        result, directory, record = self.integration_run('owner-success', hook=hook)
        self.assertEqual(result, 0)
        self.assertEqual(calls, [directory.resolve()])
        self.assertEqual(record, self.owner_record(directory))
        with self.assertRaisesRegex(ValueError, 'fresh_run_directory_required'):
            driver.execute(self.task_path, self.workspace, directory, client=object(), model='injected',
                           integration_hook=hook)
        self.assertEqual(len(calls), 1)

    def test_integration_requires_protected_accept_and_unchanged_candidate_before_callback(self):
        from unittest.mock import Mock
        for name, altered in [('verdict', {'decision': 'REJECT'}), ('digest', {'candidate_digest': '0' * 64}),
                              ('missing', {'candidate_digest': None})]:
            hook = Mock()
            _, _, record = self.integration_run('invalid-' + name, hook=hook, decision=altered)
            hook.assert_not_called()
            self.assertEqual(record['status'], 'FAILED')
            self.assertEqual(record['reason_code'], 'protected_accept_invalid')

    def test_integration_exception_digest_mismatch_and_invalid_record_fail_without_raw_text(self):
        def raised(directory):
            raise RuntimeError('private-owner-exception-must-not-be-recorded')
        def mismatched(directory):
            return {**self.owner_record(directory), 'candidate_digest': '0' * 64}
        def mutated(directory):
            record = self.owner_record(directory)
            (directory / 'candidate/product/market.py').write_text('changed after gate')
            return record
        controls = [('exception', raised, 'integration_hook_failed'),
                    ('mismatch', mismatched, 'integration_digest_mismatch'),
                    ('mutated', mutated, 'integration_digest_mismatch')]
        for name, hook, reason in controls:
            _, directory, record = self.integration_run('bad-' + name, hook=hook)
            self.assertEqual(record['status'], 'FAILED')
            self.assertEqual(record['reason_code'], reason)
            self.assertIsNone(record['integrated_head'])
            self.assertNotIn('private-owner-exception', (directory / 'integration.json').read_text())
        for name, changes in [('extra', {'provider_text': 'private raw owner text'}),
                              ('schema', {'schema': 'unexpected'}), ('status', {'status': 'ACCEPT'}),
                              ('head', {'baseline_head': '../not-a-head'}),
                              ('reason', {'reason_code': 'free text is not a fixed code'}),
                              ('receipt', {'receipt_ref': 'line1\nline2'}), ('missing-receipt', {'receipt_ref': None})]:
            with self.subTest(record=name):
                def hook(directory):
                    return {**self.owner_record(directory), **changes}
                _, _, record = self.integration_run('record-' + name, hook=hook)
                self.assertEqual(record['status'], 'FAILED')
                self.assertEqual(record['reason_code'], 'integration_record_invalid')

    def test_integration_preserves_honest_pending_or_failed_owner_status(self):
        for status in ('NOT_RECORDED', 'FAILED'):
            def hook(directory):
                return {**self.owner_record(directory), 'status': status, 'baseline_head': None,
                        'integrated_head': None, 'receipt_ref': None, 'reason_code': 'owner_not_bound'}
            _, _, record = self.integration_run('owner-' + status, hook=hook)
            self.assertEqual(record['status'], status)
            self.assertIsNone(record['integrated_head'])

    def test_integration_artifact_failure_preserves_gate_verdict_and_marks_console_failed(self):
        from factory_console import snapshot, render
        original = driver.integration_status
        for phase in ('open', 'after-write'):
            calls = []
            outside = self.root / ('outside-' + phase)
            outside.write_text('owner bytes must remain unchanged')

            def hook(directory):
                calls.append(directory)
                receipt = self.owner_record(directory)
                if phase == 'open':
                    (directory / 'integration.json').unlink()
                    (directory / 'integration.json').symlink_to(outside)
                return receipt

            def write_record(directory, callback=None):
                receipt = original(directory, callback)
                if callback is not None and phase == 'after-write':
                    raise OSError('private-filesystem-detail-must-not-be-recorded')
                return receipt

            with patch.object(driver, 'integration_status', side_effect=write_record):
                result, directory, _ = self.integration_run('write-failure-' + phase, hook=hook,
                                                             read_integration=False)
            self.assertEqual(result, 0)
            self.assertEqual(calls, [directory.resolve()])
            self.assertEqual(outside.read_text(), 'owner bytes must remain unchanged')
            public = json.loads((directory / 'console.json').read_text())
            self.assertEqual(public['state'], 'ACCEPT')
            self.assertEqual(public['integration'], {
                'status': 'FAILED', 'reason_code': 'integration_record_write_failed'})
            self.assertEqual(json.loads((directory / 'verification/decision.json').read_text())['decision'], 'ACCEPT')
            view = snapshot(directory)
            self.assertEqual(view['decision']['decision'], 'ACCEPT')
            self.assertEqual(view['integration'], public['integration'])
            page = render(view)
            self.assertIn('integration_record_write_failed', page)
            self.assertNotIn('APPLIED_RESTARTED', page)
            self.assertNotIn('private-filesystem-detail', page)
            events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1], {'stage': 'integration', 'status': 'FAILED',
                                         'action': 'integration_record_write_failed'})

    def test_integration_rejects_credentials_and_never_follows_artifact_symlink(self):
        secret = 'synthetic-integration-credential-12345678'
        def unsafe_record(directory):
            return {**self.owner_record(directory), 'receipt_ref': secret}
        with patch.dict(os.environ, {'OPENAI_API_KEY': secret}):
            _, directory, record = self.integration_run('credential-record', hook=unsafe_record)
        self.assertEqual(record['reason_code'], 'integration_record_invalid')
        self.assertNotIn(secret, (directory / 'integration.json').read_text())
        outside = self.root / 'must-remain-unchanged'
        outside.write_text('original bytes')
        run = self.root / 'symlink-artifact'
        run.mkdir()
        (run / 'integration.json').symlink_to(outside)
        with self.assertRaises(OSError):
            driver.integration_status(run)
        self.assertEqual(outside.read_text(), 'original bytes')


if __name__ == '__main__':
    unittest.main()
