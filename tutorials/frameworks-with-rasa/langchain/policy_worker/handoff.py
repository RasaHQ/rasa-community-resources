"""Expose retrieved evidence, without trusting a worker-generated conclusion."""
from .retrieval import ScopedPolicyRetriever

SCOPES = {"111111": "personal", "222222": "business"}

class PolicySession:
    def __init__(self):
        self.scope = None

    def select_demo(self, code):
        scope = SCOPES.get(code)
        if scope is None:
            return {"status": "unknown_demo_code"}
        if self.scope is not None and self.scope != scope:
            return {"status": "demo_identity_changed"}
        self.scope = scope
        return {"status": "demo_selected"}

    def retrieve(self, question):
        if self.scope is None:
            return {"status": "needs_demo_code"}
        if not isinstance(question, str) or not question.strip() or len(question) > 1000:
            return {"status": "invalid_question"}
        documents = ScopedPolicyRetriever(scope=self.scope).invoke(question)
        if not documents:
            return {"status": "no_evidence"}
        if any(d.metadata.get("scope") != self.scope for d in documents):
            return {"status": "evidence_unavailable"}
        return {"status": "sources_found", "sources": [
            {"id":d.metadata["id"], "revision":d.metadata["revision"], "quote":d.page_content}
            for d in documents
        ]}
