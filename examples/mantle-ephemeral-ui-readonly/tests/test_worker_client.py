"""Controlled private pipes, not SDK, Core conformance or live grants."""

import asyncio
import base64
from contextlib import suppress
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from lib.budget import TurnBudget, current_budget
from lib.core_process import CoreProcess
from lib.turns import TurnView, UNAVAILABLE
from lib.worker_client import ConversationBudget, WorkerClient, WorkerCleanupError
from test_turns import fixture


WORKER = r'''
import base64,json,os,time,uuid
from datetime import datetime,timezone
MODE = MODE_VALUE
PAYLOAD = PAYLOAD_VALUE
ROOT = ROOT_VALUE
print(json.dumps({'ok':1 if MODE=='readyint' else True,'outcome':'ready','protocol':'zeoconnect.poc-worker/v1'}),flush=True)
for line in __import__('sys').stdin:
    request=json.loads(line)
    with open(ROOT+'/requests','a') as log: log.write(request['method']+'\n')
    reply={'ok':True,'outcome':'completed'}
    if request['method']=='begin':
        if MODE=='slowbegin': time.sleep(3)
        if MODE=='timed_valid': time.sleep(0.04)
        inv='fixture-invocation' if MODE=='reuse' else uuid.uuid4().hex
        reply.update(operation='zeoconnect.connections.list',invocation=inv)
    elif request['method']=='read':
        if MODE=='slowread': time.sleep(3)
        if MODE=='combined': time.sleep(0.08)
        if MODE=='timed_valid': time.sleep(0.04)
        if MODE=='descendant':
            import subprocess,sys
            subprocess.Popen([sys.executable,'-c',"import time;time.sleep(.3);open("+repr(ROOT+'/late')+",'w').write('late')"])
            time.sleep(3)
        if MODE=='unbounded':
            while True: os.write(1,b'x'*65536)
        at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        PAYLOAD['in_reply_to']['invocation']=inv
        PAYLOAD['produced_at']=at
        PAYLOAD['components'][0]['snapshot'].update(observed_at=at,source={'kind':'operation','ref':inv})
        reply.update(operation='zeoconnect.connections.list',invocation=inv if MODE!='wronginv' else 'wrong',
          envelope_base64='!' if MODE=='badbase64' else base64.b64encode(json.dumps(PAYLOAD).encode()).decode())
        if MODE=='wrongop': reply['operation']='other.operation'
    elif request['method']=='contains':
        if MODE=='combined': time.sleep(0.10)
        if MODE=='timed_valid': time.sleep(0.04)
        reply['retained']=1 if MODE=='badbool' else MODE!='missing'
    encoded=json.dumps(reply)
    if MODE=='duplicate' and request['method']=='read':
        encoded=encoded.replace('"ok": true','"ok": true, "ok": true',1)
    print(encoded,flush=True)
'''


class WorkerClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def client(self, mode='normal', conversation=None):
        script = self.root / ('worker-' + mode + '.py')
        script.write_text(WORKER.replace('MODE_VALUE', repr(mode)).replace(
            'PAYLOAD_VALUE', repr(fixture())).replace('ROOT_VALUE', repr(str(self.root))))
        worker = WorkerClient(Path(sys.executable).resolve(), script,
            environment={'HOME': str(self.root), 'TMPDIR': str(self.root)},
            conversation=conversation or ConversationBudget())
        self.addCleanup(worker.close)
        return worker

    def test_retained_projection_and_next_non_tool_turn(self):
        worker = self.client()
        view = TurnView(json.loads)
        self.assertEqual(asyncio.run(worker.show(view)), {'status': 'displayed'})
        self.assertIn('Synthetic fixture', view.html)
        self.assertEqual((self.root / 'requests').read_text().splitlines(), ['begin','read','contains'])
        view.begin('non-tool', 'next')
        self.assertEqual(view.html, '')

    def test_malformed_binding_or_retention_refuses(self):
        for mode in ('wronginv','badbool','missing'):
            with self.subTest(mode=mode):
                worker=self.client(mode);view=TurnView(json.loads)
                self.assertEqual(asyncio.run(worker.show(view)), {'status':'unavailable'})
                self.assertEqual(view.html, UNAVAILABLE)
                self.assertIsNotNone(worker._process.returncode)

    def test_one_deadline_kills_worker_and_never_waits_for_socket_timeout(self):
        worker=self.client('slowread');view=TurnView(json.loads)
        with patch('lib.worker_client.WORKER_TURN_BUDGET_SECONDS',0.12):
            started=time.monotonic()
            self.assertEqual(asyncio.run(worker.show(view)), {'status':'unavailable'})
        self.assertLess(time.monotonic()-started,1)
        self.assertLess(worker._process.returncode,0)
        self.assertEqual(view.html,UNAVAILABLE)

    def test_new_turn_during_reservation_cannot_be_overwritten(self):
        worker=self.client('slowbegin');view=TurnView(json.loads)
        async def run():
            pending=asyncio.create_task(worker.show(view))
            await asyncio.sleep(0.04)
            newest=view.begin('other','newest')
            self.assertEqual(await pending,{'status':'unavailable'})
            self.assertTrue(view.is_current(newest))
        started=time.monotonic()
        asyncio.run(run())
        self.assertLess(time.monotonic()-started,1)
        self.assertEqual(view.html,'')
        self.assertLess(worker._process.returncode,0)

    def test_cancellation_reaps_worker_and_clears_lease(self):
        worker=self.client('slowread');view=TurnView(json.loads)
        async def run():
            pending=asyncio.create_task(worker.show(view))
            await asyncio.sleep(0.04);pending.cancel()
            with self.assertRaises(asyncio.CancelledError): await pending
        asyncio.run(run())
        self.assertLess(worker._process.returncode,0)
        self.assertEqual(view.html,UNAVAILABLE)

    def test_conversation_limit_and_no_reference_reuse_across_replacement(self):
        conversation=ConversationBudget()
        first=self.client('reuse',conversation)
        self.assertEqual(asyncio.run(first.show(TurnView(json.loads))),{'status':'displayed'})
        first.close()
        second=self.client('reuse',conversation)
        self.assertEqual(asyncio.run(second.show(TurnView(json.loads))),{'status':'unavailable'})
        for _ in range(6):
            worker=self.client(conversation=conversation)
            self.assertEqual(asyncio.run(worker.show(TurnView(json.loads))),{'status':'displayed'})
            worker.close()
        exhausted=self.client(conversation=conversation)
        self.assertEqual(asyncio.run(exhausted.show(TurnView(json.loads))),{'status':'unavailable'})

    def test_total_deadline_also_reaps_separate_consumer_validator(self):
        bridge=self.root/'slow-core.py'
        bridge.write_text('import os,time\nfrom pathlib import Path\nPath('+repr(str(self.root/'core-pid'))+
                          ').write_text(str(os.getpid()))\ntime.sleep(3)\nprint("{}")\n')
        core=CoreProcess(Path(sys.executable).resolve(),bridge,
                         environment={'HOME':str(self.root),'TMPDIR':str(self.root)})
        worker=self.client();view=TurnView(core)
        with patch('lib.worker_client.WORKER_TURN_BUDGET_SECONDS',0.2):
            self.assertEqual(asyncio.run(worker.show(view)),{'status':'unavailable'})
        pid=int((self.root/'core-pid').read_text())
        with self.assertRaises(ProcessLookupError): os.kill(pid,0)
        self.assertLess(worker._process.returncode,0)
        self.assertEqual(view.html,UNAVAILABLE)

    def test_core_budget_cancellation_does_not_turn_failure_into_refusal(self):
        budget=TurnBudget(time.monotonic()+0.05)
        token=current_budget.set(budget)
        try:
            budget.cancelled.set()
            core=CoreProcess(Path(sys.executable).resolve(),self.root/'not-launched.py',
                environment={'HOME':str(self.root),'TMPDIR':str(self.root)})
            with self.assertRaises(TimeoutError):core(b'fixture')
        finally:current_budget.reset(token)

    def test_read_and_retention_lookup_do_not_reset_the_deadline(self):
        worker=self.client('combined');view=TurnView(json.loads)
        with patch('lib.worker_client.WORKER_TURN_BUDGET_SECONDS',0.13):
            self.assertEqual(asyncio.run(worker.show(view)),{'status':'unavailable'})
        self.assertEqual((self.root/'requests').read_text().splitlines(),['begin','read','contains'])
        self.assertLess(worker._process.returncode,0)

    def test_timeout_kills_descendants_not_only_worker_leader(self):
        worker=self.client('descendant');view=TurnView(json.loads)
        with patch('lib.worker_client.WORKER_TURN_BUDGET_SECONDS',0.12):
            self.assertEqual(asyncio.run(worker.show(view)),{'status':'unavailable'})
        time.sleep(0.35)
        self.assertFalse((self.root/'late').exists())
        self.assertLess(worker._process.returncode,0)

    def test_denied_cleanup_is_unknown_and_never_retried_or_substituted(self):
        # No process is launched or signalled. The permission denial is an
        # injected control-path fixture, not a retry of the reported experiment.
        worker=object.__new__(WorkerClient)
        worker._process=Mock(pid=123)
        worker._close_lock=threading.Lock()
        worker._closed=False;worker._active=None
        worker.cleanup_state='NOT_REQUESTED';worker.cleanup_error=None
        denied=PermissionError(1,'Operation not permitted')
        with patch('lib.worker_client.os.killpg',side_effect=denied) as signal_call:
            with self.assertRaises(WorkerCleanupError) as first:worker.close()
            with self.assertRaises(WorkerCleanupError) as second:worker.close()
        self.assertIs(first.exception,second.exception)
        self.assertIs(first.exception.failure,denied)
        self.assertIs(first.exception.owned_process,worker._process)
        self.assertEqual(worker.cleanup_state,'UNKNOWN_SIGNAL_PERMISSION_DENIED')
        signal_call.assert_called_once()
        for method in ('wait','poll','kill','terminate'):
            getattr(worker._process,method).assert_not_called()
        worker._process.stdin.close.assert_called_once()
        worker._process.stdout.close.assert_called_once()

    def test_startup_error_survives_a_cleanup_denial(self):
        process=Mock(pid=123);startup=ValueError('worker_eof')
        with patch('lib.worker_client.subprocess.Popen',return_value=process), \
             patch('lib.worker_client.os.set_blocking'), \
             patch.object(WorkerClient,'_line',side_effect=startup), \
             patch('lib.worker_client.os.killpg',side_effect=PermissionError(1,'Operation not permitted')) as signal_call:
            with self.assertRaises(WorkerCleanupError) as caught:
                WorkerClient(Path('/host/python'),Path('/host/launcher'),
                    environment={'HOME':str(self.root),'TMPDIR':str(self.root)},
                    conversation=ConversationBudget())
        self.assertIs(caught.exception.startup_error,startup)
        self.assertIsInstance(caught.exception.failure,PermissionError)
        self.assertIs(caught.exception.owned_process,process)
        signal_call.assert_called_once();process.wait.assert_not_called()

    def read_failure(self, mode, reason):
        worker=self.client(mode)
        budget=TurnBudget(time.monotonic()+5)
        invocation=worker._begin(budget)
        with self.assertRaisesRegex(ValueError, '^'+reason+'$'):
            worker._read(invocation,budget)

    def test_duplicate_key_in_otherwise_exact_read_reply(self):
        # The reply contains every correct read field, and differs only by
        # a second identical ok key. Without the duplicate guard it is valid.
        self.read_failure('duplicate','duplicate_reply_key')

    def test_base64_decoder_guard_is_not_masked_by_view_policy(self):
        # validate=False would decode ! into an empty byte string. Calling
        # _read directly ensures no later view/schema guard can hide that bug.
        self.read_failure('badbase64','worker_envelope_invalid')

    def test_unbounded_writer_hits_size_guard_not_timeout_or_eof(self):
        self.read_failure('unbounded','worker_reply_bound')

    def line_from(self, raw):
        # Atomic small write gives _line exactly one chunk, with no process.
        reader,writer=os.pipe()
        try:
            os.write(writer,raw)
        finally:
            os.close(writer)
        with os.fdopen(reader,'rb',buffering=0) as source:
            worker=object.__new__(WorkerClient)
            worker._closed=False;worker._process=Mock(stdout=source)
            return worker._line(TurnBudget(time.monotonic()+5))

    def test_line_framing_and_json_guards_are_independent(self):
        self.assertEqual(self.line_from(b'{}\n'),{})
        for raw in (b'{}\ntrailing',b'{}\n{}\n',b'\xef\xbb\xbf{}\n'):
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'^worker_reply_framing$'):
                self.line_from(raw)
        with self.assertRaisesRegex(ValueError,'^invalid_number$'):
            self.line_from(b'{"value":NaN}\n')
        with self.assertRaisesRegex(ValueError,'^worker_reply_object$'):
            self.line_from(b'[]\n')

    def test_exact_response_fields_and_boolean_identity(self):
        valid={'ok':True,'outcome':'completed','operation':'zeoconnect.connections.list','invocation':'valid'}
        cases=[dict(valid,extra='not allowed'),{k:v for k,v in valid.items() if k!='invocation'},
               dict(valid,ok=1),dict(valid,outcome='ready')]
        for reply in cases:
            with self.subTest(reply=reply):
                worker=self.client()
                with patch.object(worker,'_line',return_value=reply):
                    with self.assertRaisesRegex(ValueError,'^worker_refused_or_invalid$'):
                        worker._exchange({'method':'begin'},{'operation','invocation'},TurnBudget(time.monotonic()+5))

    def test_ready_numeric_one_is_not_boolean_true(self):
        with self.assertRaisesRegex(ValueError,'^worker_not_ready$'):
            self.client('readyint')

    def test_request_byte_and_request_count_caps_precede_exchange(self):
        valid={'ok':True,'outcome':'completed','operation':'zeoconnect.connections.list','invocation':'valid'}
        for request,count,reason in [({'method':'begin','padding':'x'*1024},0,'worker_request_bound'),
                                     ({'method':'begin'},32,'worker_unavailable')]:
            with self.subTest(reason=reason):
                worker=self.client();worker._requests=count
                with patch.object(worker,'_line',return_value=valid) as read_reply:
                    with self.assertRaisesRegex(ValueError,'^'+reason+'$'):
                        worker._exchange(request,{'operation','invocation'},TurnBudget(time.monotonic()+5))
                read_reply.assert_not_called()

    def test_parallel_exchange_is_refused_before_another_write(self):
        worker=self.client();worker._exchange_lock.acquire()
        try:
            with self.assertRaisesRegex(ValueError,'^concurrent_worker_exchange$'):
                worker._exchange({'method':'begin'},{'operation','invocation'},TurnBudget(time.monotonic()+5))
        finally:
            if worker._exchange_lock.locked():worker._exchange_lock.release()
        self.assertLess(worker._process.returncode,0)
        self.assertFalse((self.root/'requests').exists())

    def test_concurrent_show_refuses_without_waiting_for_first_deadline(self):
        worker=self.client('slowread');view=TurnView(json.loads)
        async def run():
            pending=asyncio.create_task(worker.show(view))
            try:
                deadline=time.monotonic()+1
                while not (self.root/'requests').exists() or 'read' not in (self.root/'requests').read_text():
                    if time.monotonic()>deadline:self.fail('fixture did not reach read')
                    await asyncio.sleep(0.005)
                # Far from the first seven-second deadline and its 3s read.
                try:
                    result=await asyncio.wait_for(worker.show(view),timeout=0.5)
                except TimeoutError:
                    self.fail('concurrent show waited instead of refusing immediately')
                self.assertEqual(result,{'status':'unavailable'})
                self.assertEqual(await asyncio.wait_for(pending,timeout=0.5),{'status':'unavailable'})
            finally:
                worker.close()
                if not pending.done():pending.cancel()
                with suppress(asyncio.CancelledError):await pending
        asyncio.run(run())

    def test_invocation_shape_guard_without_other_protocol_checks(self):
        for invocation in ('','space here','x'*257,'non-ascii-\u00e9',None,True):
            with self.subTest(invocation=invocation),self.assertRaisesRegex(ValueError,'^invalid_invocation$'):
                ConversationBudget().bind(invocation)
        ConversationBudget().bind('valid._:/-123')

    def test_wrong_operation_during_reservation_and_read(self):
        worker=self.client()
        with patch.object(worker,'_exchange',return_value={'operation':'wrong','invocation':'valid'}):
            with self.assertRaisesRegex(ValueError,'^worker_operation$'):
                worker._begin(TurnBudget(time.monotonic()+5))
        self.read_failure('wrongop','worker_result_binding')

    def test_encoded_and_decoded_envelope_bounds(self):
        worker=self.client();budget=TurnBudget(time.monotonic()+5)
        operation='zeoconnect.connections.list';invocation='valid'
        limit=4*((262144+2)//3)
        too_long='A'*(limit+4)
        reply={'operation':operation,'invocation':invocation,'envelope_base64':too_long}
        with patch.object(worker,'_exchange',return_value=reply), \
             patch('lib.worker_client.base64.b64decode',wraps=base64.b64decode) as decode:
            with self.assertRaisesRegex(ValueError,'^worker_envelope_bound$'):worker._read(invocation,budget)
        decode.assert_not_called()
        # MAX_BYTES+1 has the same encoded length as MAX_BYTES, so this reaches
        # the decoded-size guard without failing the preceding encoded cap.
        reply['envelope_base64']=base64.b64encode(b'x'*262145).decode()
        self.assertEqual(len(reply['envelope_base64']),limit)
        with patch.object(worker,'_exchange',return_value=reply):
            with self.assertRaisesRegex(ValueError,'^worker_envelope_bound$'):worker._read(invocation,budget)
        reply['envelope_base64']=base64.b64encode(b'x'*262144).decode()
        with patch.object(worker,'_exchange',return_value=reply):
            self.assertEqual(len(worker._read(invocation,budget).envelope),262144)

    def test_constructor_rejects_unowned_paths_env_and_startup_timeout_before_launch(self):
        valid={'python':Path('/host/python'),'launcher':Path('/host/launcher'),
               'environment':{'HOME':str(self.root),'TMPDIR':str(self.root)},
               'conversation':ConversationBudget()}
        path_reason='absolute owned interpreter and launcher required'
        env_reason='isolated environment required'
        timeout_reason='invalid startup timeout'
        cases=[({'python':Path('relative/python')},path_reason),
               ({'launcher':Path('relative/launcher')},path_reason),
               ({'environment':{'HOME':str(self.root)}},env_reason),
               ({'environment':{'TMPDIR':str(self.root)}},env_reason),
               ({'environment':dict(valid['environment'],PATH='/untrusted')},env_reason),
               ({'startup_timeout':0},timeout_reason),({'startup_timeout':6},timeout_reason)]
        for change,reason in cases:
            with self.subTest(change=change),patch('lib.worker_client.subprocess.Popen',side_effect=AssertionError('must not launch')) as launch:
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):WorkerClient(**(valid|change))
                launch.assert_not_called()

    def test_bind_race_after_reservation_with_far_deadline(self):
        worker=self.client();view=TurnView(json.loads);newest=[]
        begin=worker._begin
        def supersede_after_reservation(budget):
            invocation=begin(budget)
            self.assertGreater(budget.deadline-time.monotonic(),5)
            newest.append(view.begin('other','newer-turn'))
            return invocation
        with patch.object(worker,'_begin',side_effect=supersede_after_reservation), \
             patch.object(worker,'_read',wraps=worker._read) as read:
            self.assertEqual(asyncio.run(worker.show(view)),{'status':'unavailable'})
        read.assert_not_called()
        self.assertTrue(view.is_current(newest[0]))
        self.assertEqual(view.html,'')
        self.assertEqual((self.root/'requests').read_text().splitlines(),['begin'])

    def test_timed_valid_path_completes_within_shared_budget(self):
        worker=self.client('timed_valid');view=TurnView(json.loads)
        with patch('lib.worker_client.WORKER_TURN_BUDGET_SECONDS',0.6):
            start=time.monotonic()
            self.assertEqual(asyncio.run(worker.show(view)),{'status':'displayed'})
            elapsed=time.monotonic()-start
        self.assertGreaterEqual(elapsed,0.10)
        self.assertLess(elapsed,0.6)
