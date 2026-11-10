"""Native LangChain controls. Scripted responses are not provider accuracy evidence."""
import json
import unittest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from policy_worker.retrieval import ScopedPolicyRetriever, DOCUMENTS
from policy_worker.pipeline import answer_policy

class CountedFixtureModel(FakeListChatModel):
    calls: int = 0
    def _call(self, *args, **kwargs):
        self.calls += 1
        return super()._call(*args, **kwargs)

class NativeRetrievalControls(unittest.TestCase):
    def setUp(self):
        self.retriever = ScopedPolicyRetriever(scope="personal")
        d=DOCUMENTS[0]
        self.answer={"answer":"The personal-card policy allows replacement.","citations":[{"id":d.metadata['id'],"revision":d.metadata['revision'],"quote":d.page_content}]}
        self.model=CountedFixtureModel(responses=[json.dumps(self.answer)])

    def test_native_retriever_retains_document_metadata(self):
        docs=self.retriever.invoke("Replace a damaged card")
        self.assertEqual([d.metadata['id'] for d in docs],["P-101"])
        self.assertEqual(docs[0].metadata['revision'],"2026-10-11")

    def test_native_prompt_model_pipeline_returns_checked_evidence(self):
        result=answer_policy("Replace a damaged card",self.retriever,self.model,"personal")
        self.assertEqual(result['status'],'evidence_checked')
        self.assertEqual(self.model.calls,1)
        self.assertEqual(result['citations'][0]['id'],'P-101')

    def test_scope_mismatch_refused_before_model(self):
        business=ScopedPolicyRetriever(scope="business")
        self.assertEqual(answer_policy("Replace card",business,self.model,"personal"),{'status':'evidence_unavailable'})
        self.assertEqual(self.model.calls,0)

    def test_no_documents_does_not_call_model(self):
        self.assertEqual(answer_policy("Mortgage question",self.retriever,self.model,"personal"),{'status':'no_evidence'})
        self.assertEqual(self.model.calls,0)

    def test_native_model_fabricated_citation_refused(self):
        self.answer['citations'][0]['id']='B-201'
        self.model.responses=[json.dumps(self.answer)]
        self.assertEqual(answer_policy("Replace card",self.retriever,self.model,"personal"),{'status':'evidence_unavailable'})

if __name__ == "__main__":unittest.main()
