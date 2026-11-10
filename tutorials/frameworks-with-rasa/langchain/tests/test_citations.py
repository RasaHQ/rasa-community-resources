import copy
import json
import unittest
from dataclasses import dataclass
from policy_worker.citations import validate_answer

@dataclass
class DocumentFixture:
    page_content: str
    metadata: dict

class CitationControls(unittest.TestCase):
    def setUp(self):
        self.doc = DocumentFixture("A damaged personal debit card can be replaced.", {"id":"P-101", "scope":"personal", "revision":"2026-10-11"})
        self.answer = {"answer":"A replacement can be requested.", "citations":[{"id":"P-101", "revision":"2026-10-11", "quote":self.doc.page_content}]}

    def result(self, answer=None, documents=None):
        return validate_answer(json.dumps(self.answer if answer is None else answer), [self.doc] if documents is None else documents, "personal")

    def test_exact_quote_and_revision_pass(self):
        self.assertEqual(self.result()["status"],"evidence_checked")

    def test_fabricated_citation_refused(self):
        self.answer["citations"][0]["id"]="P-999"
        self.assertEqual(self.result(),{"status":"evidence_unavailable"})

    def test_fabricated_quote_refused(self):
        self.answer["citations"][0]["quote"]="All replacement cards are completely free."
        self.assertEqual(self.result(),{"status":"evidence_unavailable"})

    def test_old_revision_refused(self):
        self.answer["citations"][0]["revision"]="2025-10-11"
        self.assertEqual(self.result(),{"status":"evidence_unavailable"})

    def test_other_scope_refused(self):
        self.doc.metadata["scope"]="business"
        self.assertEqual(self.result(),{"status":"evidence_unavailable"})

    def test_empty_duplicate_or_extra_fields_refused(self):
        for citations in [[],self.answer["citations"]*2,[{**self.answer["citations"][0],"action":"replace_card"}]]:
            with self.subTest(citations=citations):
                answer={**self.answer,"citations":citations}
                self.assertEqual(self.result(answer),{"status":"evidence_unavailable"})

    def test_duplicate_document_id_refused(self):
        self.assertEqual(self.result(documents=[self.doc,copy.deepcopy(self.doc)]),{"status":"evidence_unavailable"})

    def test_wrong_schema_and_non_json_refused(self):
        for raw in ['[]','null','not JSON',json.dumps({**self.answer,"tool_call":"cancel"})]:
            with self.subTest(raw=raw):self.assertEqual(validate_answer(raw,[self.doc],"personal"),{"status":"evidence_unavailable"})

    def test_exact_quote_does_not_prove_answer_entailment(self):
        self.answer["answer"]="Your card has already been replaced."
        # This guard verifies citation identity/quote membership only. A separate
        # semantic check and action boundary are still required; preserve this limit.
        self.assertEqual(self.result()["status"],"evidence_checked")

if __name__ == "__main__":unittest.main()
