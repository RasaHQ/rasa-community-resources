"""Keep LangChain retrieval, prompt and supplied model in the worker."""
from langchain_core.prompts import ChatPromptTemplate
from .citations import validate_answer

PROMPT = ChatPromptTemplate.from_messages([
    ("system", "Answer the policy question using only the supplied documents. Return JSON with exactly answer and citations. Each citation has id, revision and an exact quote from a supplied document. Do not perform account actions."),
    ("human", "Question: {question}\nDocuments: {documents}"),
])


def answer_policy(question, retriever, model, scope):
    if not isinstance(question, str) or not question.strip() or len(question) > 1000:
        return {"status": "invalid_question"}
    documents = retriever.invoke(question)
    if not documents:
        return {"status": "no_evidence"}
    # Reject a faulty retriever before a model sees another scope's content.
    if any(doc.metadata.get("scope") != scope for doc in documents):
        return {"status": "evidence_unavailable"}
    context = "\n\n".join(f"{d.metadata['id']} revision {d.metadata['revision']}: {d.page_content}" for d in documents)
    response = (PROMPT | model).invoke({"question": question, "documents": context})
    if not isinstance(response.content, str):
        return {"status": "evidence_unavailable"}
    return validate_answer(response.content, documents, scope)
