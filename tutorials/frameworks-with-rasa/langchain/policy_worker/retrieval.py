"""A native LangChain retriever; account scope is supplied by the application."""
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

DOCUMENTS = (
    Document(page_content="A damaged personal debit card can be replaced. The existing card remains active until the replacement is activated.", metadata={"id": "P-101", "scope": "personal", "revision": "2026-10-11"}),
    Document(page_content="A business debit card replacement needs the nominated company administrator's approval.", metadata={"id": "B-201", "scope": "business", "revision": "2026-10-11"}),
)

class ScopedPolicyRetriever(BaseRetriever):
    scope: str

    def _get_relevant_documents(self, query, *, run_manager):
        if self.scope not in {"personal", "business"}:
            raise ValueError("unknown document scope")
        if "card" not in query.lower():
            return []
        # Replace this fixture search with the existing authorised retriever.
        # Scope filtering belongs before prompt construction, not after generation.
        return [d.model_copy(deep=True) for d in DOCUMENTS if d.metadata["scope"] == self.scope]
