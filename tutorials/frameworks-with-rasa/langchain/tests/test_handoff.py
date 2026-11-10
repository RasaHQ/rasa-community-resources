import ast
import inspect
import unittest
from unittest.mock import patch
from policy_worker.handoff import PolicySession
from policy_worker.retrieval import DOCUMENTS
import policy_worker.handoff as handoff

class RetrievalHandoffControls(unittest.TestCase):
    def setUp(self):
        self.session=PolicySession()

    def test_missing_demo_blocks_retrieval(self):
        self.assertEqual(self.session.retrieve("Replace card"),{'status':'needs_demo_code'})

    def test_personal_and_business_keep_separate_sources(self):
        for code,identity in [('111111','P-101'),('222222','B-201')]:
            with self.subTest(code=code):
                session=PolicySession();session.select_demo(code)
                result=session.retrieve('Replace card')
                self.assertEqual([s['id'] for s in result['sources']],[identity])
                self.assertEqual(result['sources'][0]['revision'],'2026-10-11')

    def test_changed_demo_cannot_rebind_sources(self):
        self.session.select_demo('111111')
        self.assertEqual(self.session.select_demo('222222'),{'status':'demo_identity_changed'})
        self.assertEqual(self.session.retrieve('Replace card')['sources'][0]['id'],'P-101')

    def test_faulty_retriever_wrong_scope_refused(self):
        self.session.select_demo('111111')
        with patch.object(handoff.ScopedPolicyRetriever,'invoke',return_value=[DOCUMENTS[1]]):
            self.assertEqual(self.session.retrieve('Replace card'),{'status':'evidence_unavailable'})

    def test_removing_scope_guard_exposes_business_source(self):
        source=inspect.getsource(handoff);tree=ast.parse(source)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PolicySession')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='retrieve')
        guards=[n for n in method.body if isinstance(n,ast.If) and isinstance(n.test,ast.Call) and isinstance(n.test.func,ast.Name) and n.test.func.id=='any']
        self.assertEqual(len(guards),1);method.body.remove(guards[0]);ast.fix_missing_locations(tree)
        namespace={'__name__':'policy_worker.controlled_mutation','__package__':'policy_worker'}
        exec(compile(tree,'controlled-scope-removal','exec'),namespace)
        session=namespace['PolicySession']();session.select_demo('111111')
        with patch.object(handoff.ScopedPolicyRetriever,'invoke',return_value=[DOCUMENTS[1]]):
            result=session.retrieve('Replace card')
        # This intentionally breaks our application guard, not LangChain.
        self.assertEqual(result['sources'][0]['id'],'B-201')
        self.assertIn('company administrator',result['sources'][0]['quote'])

    def test_handoff_uses_retrieval_without_worker_generation(self):
        self.session.select_demo('111111')
        result=self.session.retrieve('Replace card')
        self.assertEqual(set(result),{'status','sources'})
        self.assertNotIn('answer',result)

if __name__ == '__main__':unittest.main()
