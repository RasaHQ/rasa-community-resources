"""Behavioral regressions for after-class hardening; no provider calls."""
import asyncio
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import factory_gate
import launcher

class CopyAndLoggingTests(unittest.TestCase):
    def test_both_factory_modes_exclude_nested_dotenv_files(self):
        for mode in ['SCRIPTED','LIVE']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);pack=root/'pack';(pack/'tasks').mkdir(parents=True)
                (pack/'tasks/b-limit-currencies.json').write_text('{"limit":2}')
                (pack/'keep.txt').write_text('retained')
                for name in ['.env','.env.local','tasks/.env','tasks/.env.secret']:
                    (pack/name).write_text('synthetic-only')
                keyfile=root/'owner.env';keyfile.write_text('OPENAI_API_KEY=synthetic-only\n')
                copied=[]
                def command(args,cwd,timeout,**kwargs):
                    if args[0]=='-c':return 0,'',''
                    work=Path(cwd);copied.append(work)
                    self.assertTrue((work/'keep.txt').is_file())
                    self.assertEqual(list(work.rglob('.env*')),[])
                    return 2,'',''
                with patch.object(factory_gate,'_pack',return_value=pack),patch.object(factory_gate,'_run',side_effect=command):
                    factory_gate.run_factory('good',mode=mode,evidence_root=root/'evidence',env_file=keyfile)
                self.assertEqual(len(copied),1)
    def test_log_write_or_flush_failure_does_not_stop_draining(self):
        for fail_at in ['write','flush']:
            with self.subTest(fail_at=fail_at):
                child=MagicMock();child.stdout=io.BytesIO(b'first\nsecond\nthird\n')
                log=MagicMock();getattr(log,fail_at).side_effect=OSError('synthetic disk failure')
                launcher.capture_log(child,log,{})
                self.assertEqual(child.stdout.read(),b'')
                self.assertEqual(log.write.call_count,1)

spec=importlib.util.spec_from_file_location('factory_authoritative_hooks',Path(__file__).parent/'project/hooks.py')
hooks=importlib.util.module_from_spec(spec);spec.loader.exec_module(hooks)
from rasa.mantle.hooks import IncomingMessagePayload, ModelResponsePayload, ToolResultPayload

class AuthoritativeReplyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):hooks._pending.clear()
    def record(self):return dict(verdict='REJECT',failing_test='test_b1_four_currencies_show_at_most_the_limit',fingerprint='a'*64,builder_calls=0,seconds=1.25,mode='SCRIPTED')
    async def result(self,value,**changes):
        kwargs=dict(sender_id='alice',tool_name='mcp/factory:run_factory',arguments={},value=value);kwargs.update(changes)
        await hooks.remember_factory_result(ToolResultPayload(**kwargs))
    async def test_conflicting_model_verdict_is_replaced_with_actual_tool_quote(self):
        record=self.record();await self.result({'content':[{'text':json.dumps(record)}]})
        out=await hooks.buffered_scripted_reply(ModelResponsePayload(sender_id='alice',text='ACCEPT, everything deployed'))
        self.assertNotIn('ACCEPT',out.text);self.assertIn('Nothing was deployed.',out.text)
        quoted=out.text.split('\n',1)[1].rsplit('\n',1)[0];self.assertEqual(json.loads(quoted),record)
    async def test_invalid_or_failed_result_cannot_become_accept(self):
        for value,error in [('garbage',False),({'verdict':'ACCEPT'},False),(self.record(),True)]:
            await self.result(value,is_error=error)
            out=await hooks.buffered_scripted_reply(ModelResponsePayload(sender_id='alice',text='ACCEPT'))
            self.assertIn('NOT_READY',out.text);self.assertNotIn('ACCEPT',out.text)
    async def test_sender_isolation_and_tool_only_iteration(self):
        await self.result(self.record())
        other=ModelResponsePayload(sender_id='bob',text='Hello')
        self.assertEqual(await hooks.buffered_scripted_reply(other),other)
        tool_only=ModelResponsePayload(sender_id='alice',tool_calls=[{'id':'next'}])
        self.assertEqual(await hooks.buffered_scripted_reply(tool_only),tool_only)
        out=await hooks.buffered_scripted_reply(ModelResponsePayload(sender_id='alice',text='made up'))
        self.assertIn('REJECT',out.text)
    async def test_new_turn_cannot_reuse_an_unfinished_previous_result(self):
        await self.result(self.record())
        await hooks.clear_previous_turn(IncomingMessagePayload(sender_id='alice',text='hello'))
        payload=ModelResponsePayload(sender_id='alice',text='Hello')
        self.assertEqual(await hooks.buffered_scripted_reply(payload),payload)
