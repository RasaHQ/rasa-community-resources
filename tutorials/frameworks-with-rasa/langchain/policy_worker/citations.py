"""Validate returned evidence without claiming semantic answer correctness."""
import json


def validate_answer(raw, documents, scope):
    try:
        answer = json.loads(raw)
        if not isinstance(answer, dict) or set(answer) != {"answer", "citations"}:
            raise ValueError("shape")
        if not isinstance(answer["answer"], str) or not answer["answer"].strip() or len(answer["answer"]) > 2000:
            raise ValueError("answer")
        citations = answer["citations"]
        if not isinstance(citations, list) or not 1 <= len(citations) <= 4:
            raise ValueError("citations")
        allowed = {}
        for doc in documents:
            if doc.metadata.get("scope") != scope:
                raise ValueError("retrieval scope")
            identity = doc.metadata["id"]
            if identity in allowed:
                raise ValueError("duplicate document identity")
            allowed[identity] = doc
        seen = set()
        for cite in citations:
            if not isinstance(cite, dict) or set(cite) != {"id", "revision", "quote"}:
                raise ValueError("citation shape")
            if not all(isinstance(cite[k], str) for k in cite):
                raise ValueError("citation type")
            identity = cite["id"]
            doc = allowed.get(identity)
            quote = cite["quote"]
            if doc is None or identity in seen or cite["revision"] != doc.metadata["revision"]:
                raise ValueError("citation identity")
            if len(quote.strip()) < 20 or quote not in doc.page_content:
                raise ValueError("quotation")
            seen.add(identity)
        return {"status": "evidence_checked", **answer}
    except (ValueError, TypeError, KeyError):
        # Do not leak rejected answer/citations to the customer-facing model.
        return {"status": "evidence_unavailable"}
