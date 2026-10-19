"""Controlled private pipes, not SDK, Core conformance or live grants."""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from lib.budget import TurnBudget, current_budget
from lib.core_process import CoreProcess
from lib.turns import TurnView, UNAVAILABLE
from lib.worker_client import ConversationBudget, WorkerClient
from test_turns import fixture


WORKER = r'''
import base64,json,os,time,uuid
from datetime import datetime,timezone
MODE = MODE_VALUE
PAYLOAD = PAYLOAD_VALUE
ROOT = ROOT_VALUE
print('{"ok":true,"outcome":"ready","protocol":"zeoconnect.poc-worker/v1"}',flush=True)
for line in __import__('sys').stdin:
    request=json.loads(line)
    with open(ROOT+'/requests','a') as log: log.write(request['method']+'\n')
    reply={'ok':True,'outcome':'completed'}
    if request['method']=='begin':
        if MODE=='slowbegin': time.sleep(3)
        inv='fixture-invocation' if MODE=='reuse' else uuid.uuid4().hex
        reply.update(operation='zeoconnect.connections.list',invocation=inv)
    elif request['method']=='read':
        if MODE=='slowread': time.sleep(3)
        if MODE=='combined': time.sleep(0.08)
        if MODE=='descendant':
            import subprocess,sys
            subprocess.Popen([sys.executable,'-c',"import time;time.sleep(.3);open("+repr(ROOT+'/late')+",'w').write('late')"])
            time.sleep(3)
        if MODE=='unbounded':
            while True: os.write(1,b'x'*65536)
        if MODE=='duplicate':
            print('{"ok":true,"ok":true,"outcome":"completed"}',flush=True);continue
        at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        PAYLOAD['in_reply_to']['invocation']=inv
        PAYLOAD['produced_at']=at
        PAYLOAD['components'][0]['snapshot'].update(observed_at=at,source={'kind':'operation','ref':inv})
        reply.update(operation='zeoconnect.connections.list',invocation=inv if MODE!='wronginv' else 'wrong',
          envelope_base64='!' if MODE=='badbase64' else base64.b64encode(json.dumps(PAYLOAD).encode()).decode())
    elif request['method']=='contains':
        if MODE=='combined': time.sleep(0.10)
        reply['retained']=1 if MODE=='badbool' else MODE!='missing'
    print(json.dumps(reply),flush=True)
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

    def test_malformed_binding_duplicates_base64_and_boolean_refuse(self):
        for mode in ('wronginv','duplicate','badbase64','badbool','missing','unbounded'):
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
        asyncio.run(run())
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
