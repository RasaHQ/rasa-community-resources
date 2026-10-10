"""Actual Deep Agents graph with deterministic model responses, no provider use."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from bank_research.casework import CaseSession
from bank_research.researcher import create_researcher, validate_result, investigate

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    NATIVE = True
except ImportError:
    NATIVE = False


@unittest.skipUnless(NATIVE, 'Run in the separate locked Deep Agents worker environment')
class ActualGraph(unittest.IsolatedAsyncioTestCase):
    async def test_native_graph_reads_selected_evidence_without_write_tools(self):
        session = CaseSession();session.verify_demo('111111');session.select('TX-101')
        evidence = session.evidence()
        offered = set()
        outputs = [
            AIMessage(content='', tool_calls=[{'name': 'read_case_evidence', 'args': {'evidence_id': name}, 'id': 'call-'+name, 'type':'tool_call'} for name in evidence]),
            AIMessage(content=json.dumps({'evidence_ids': list(evidence)})),
        ]
        async def response(model, messages, **kwargs):
            offered.update(item['function']['name'] for item in kwargs.get('tools', []))
            return ChatResult(generations=[ChatGeneration(message=outputs.pop(0))])
        model = ChatOpenAI(model='gpt-5.5-2026-04-23', api_key='offline-placeholder', use_responses_api=True)
        with patch.object(ChatOpenAI, '_agenerate', response):
            graph = create_researcher(evidence, model)
            result = await investigate(evidence, graph)
        self.assertEqual(result['status'], 'research_complete')
        self.assertEqual(result['evidence'], evidence)
        self.assertIn('read_case_evidence', offered)
        self.assertFalse(offered & {'execute','task','read_file','write_file','ls','edit_file','glob','grep','submit_review'})
        self.assertEqual(session.submitted, {})

    async def test_native_read_tool_refuses_other_case_reference(self):
        session=CaseSession();session.verify_demo('111111');session.select('TX-101')
        evidence=session.evidence()
        outputs=[AIMessage(content='', tool_calls=[{'name':'read_case_evidence','args':{'evidence_id':'TX-201'},'id':'other','type':'tool_call'}]), AIMessage(content='{"evidence_ids":["TX-201"]}')]
        async def response(model,messages,**kwargs):
            return ChatResult(generations=[ChatGeneration(message=outputs.pop(0))])
        with patch.object(ChatOpenAI,'_agenerate',response):
            result=await investigate(evidence,create_researcher(evidence,ChatOpenAI(model='gpt-5.5-2026-04-23',api_key='offline-placeholder')))
        self.assertEqual(result['error'],'research_unavailable')


class OutputBoundary(unittest.TestCase):
    def test_model_decisions_are_dropped(self):
        evidence={'transaction': {'amount':'49.00'}}
        value=validate_result({'messages':[SimpleNamespace(content='{"evidence_ids":["transaction"],"decision":"refund","submit_review":true}')]}, evidence)
        self.assertNotIn('decision',value)
        self.assertEqual(value['evidence'],evidence)

    def test_responses_text_blocks_are_parsed(self):
        value=validate_result({'messages':[SimpleNamespace(content=[{'type':'text','text':'{"evidence_ids":["transaction"]}'}])]},{'transaction':{'amount':'49.00'}})
        self.assertEqual(value['status'],'research_complete')

    def test_forged_reference_refused(self):
        with self.assertRaises(ValueError):
            validate_result({'messages':[SimpleNamespace(content='{"evidence_ids":["other-customer"]}')]},{'transaction':{}})

    def test_empty_or_malformed_report_refused(self):
        for body in ('{"evidence_ids":[]}', 'not json', '{"evidence_ids":[{}]}'):
            with self.assertRaises((ValueError,TypeError)):
                validate_result({'messages':[SimpleNamespace(content=body)]},{'transaction':{}})

if __name__=='__main__': unittest.main()
