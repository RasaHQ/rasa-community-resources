"""Native gate and invoker with a controlled tracker; not a model conversation."""
import importlib.util
import json
import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from bank_research.casework import CaseSession
PROJECT=Path(__file__).resolve().parents[1]/'mantle'
NATIVE=importlib.util.find_spec('rasa') is not None


@unittest.skipUnless(NATIVE,'Run with the locked Mantle interpreter')
class ConfirmationControl(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import yaml
        from rasa.mantle.skills.conditions import GatedTool
        from rasa.mantle.orchestration.tool_execution.constraints import ToolConfirmationGate
        from rasa.mantle.orchestration.tool_execution.invoker import ToolInvoker
        spec=importlib.util.spec_from_file_location('charge_review_tools',PROJECT/'skills/charge_review/tools.py')
        self.tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.tools)
        self.case=CaseSession();self.case.verify_demo('111111');self.case.select('TX-101')
        proposal=self.case.prepare()
        self.args={key:proposal[key] for key in ('proposal_id','merchant','amount','currency','date')}
        self.patch=patch.object(self.tools,'session',return_value=self.case);self.patch.start();self.addCleanup(self.patch.stop)
        self.tracker=SimpleNamespace(active_frame=None,pending_tool_confirmation=None,memory_scope=lambda:('charge_review','charge_review'),recording_write=lambda **kwargs:nullcontext(),apply_events=lambda events:None)
        self.tracker.pending_tool_confirmation_for_active_frame=lambda:self.tracker.pending_tool_confirmation
        self.tracker.set_pending_tool_confirmation=lambda pending:setattr(self.tracker,'pending_tool_confirmation',pending)
        self.tracker.clear_pending_tool_confirmation=lambda:setattr(self.tracker,'pending_tool_confirmation',None)
        settings=yaml.safe_load((PROJECT/'skills/charge_review/skill.md').read_text().split('---',2)[1])['tool_constraints'][0]['submit_review']
        self.definition=GatedTool(name='submit_review',**settings)
        invoker=ToolInvoker(mcp_runtime=None,tool_timeout=25,verbatim_trigger_evaluator=SimpleNamespace(queue_tool_outcome=lambda **kwargs:None))
        self.gate=ToolConfirmationGate({'charge_review':{'submit_review':self.tools.submit_review}},invoker,lambda *args:None)

    def pause(self):
        result=self.gate.gate_builder_tool(tool_gate=self.definition,tool_name='submit_review',tool_args=self.args,tracker_handle=self.tracker,skill_id='charge_review')
        self.assertIsNotNone(self.tracker.pending_tool_confirmation)
        self.assertEqual(self.case.submitted,{})
        return result

    async def test_same_turn_cannot_approve_original_request(self):
        self.pause()
        result,complete=await self.gate.dispatch_resolve({'confirmed':True},self.tracker)
        self.assertFalse(complete);self.assertIn('same turn',result);self.assertEqual(self.case.submitted,{})
        print(f'same-turn approval | recorded={len(self.case.submitted)}')

    async def test_denial_does_not_invoke_submission(self):
        self.pause();self.gate.begin_user_turn()
        result,complete=await self.gate.dispatch_resolve({'confirmed':False},self.tracker)
        self.assertTrue(complete);self.assertEqual(self.case.submitted,{})

    async def test_next_turn_confirmation_runs_native_binding(self):
        self.pause();self.gate.begin_user_turn()
        result,complete=await self.gate.dispatch_resolve({'confirmed':True},self.tracker)
        self.assertTrue(complete);self.assertEqual(json.loads(result)['status'],'demo_recorded')
        self.assertEqual(len(self.case.submitted),1)
        print(f'next-turn approval | recorded={len(self.case.submitted)}')

    async def test_pending_old_confirmation_cannot_submit_corrected_charge(self):
        self.pause();self.case.select('TX-102');self.gate.begin_user_turn()
        result,complete=await self.gate.dispatch_resolve({'confirmed':True},self.tracker)
        self.assertEqual(json.loads(result)['error'],'proposal_changed_or_missing')
        print(f'corrected charge | recorded={len(self.case.submitted)} | error={json.loads(result)["error"]}')
        self.assertEqual(self.case.submitted,{})

    async def test_changed_readback_refused_through_native_binding(self):
        self.args['amount']='149.00';self.pause();self.gate.begin_user_turn()
        result,complete=await self.gate.dispatch_resolve({'confirmed':True},self.tracker)
        self.assertEqual(json.loads(result)['error'],'readback_changed')

    async def test_research_result_discarded_after_selection_changes(self):
        async def research(evidence):
            self.case.select('TX-102')
            return {'status':'research_complete','evidence':evidence}
        with patch.object(self.tools,'investigate',research):
            result=await self.tools.research_charge()
        self.assertEqual(result.llm_response['error'],'selection_changed_during_research')

if __name__=='__main__':unittest.main()
