"""Bind public claim type in application state, then inspect native task records."""

from .acceptance import PUBLIC_SOURCES, inspect_result


class ClaimSession:
    def __init__(self, crew_factory):
        self.crew_factory = crew_factory
        self.claim_type = None

    def select(self, claim_type):
        if claim_type not in PUBLIC_SOURCES:
            return {"status": "unknown_claim_type"}
        if self.claim_type is not None and self.claim_type != claim_type:
            return {"status": "claim_type_changed"}
        self.claim_type = claim_type
        return {"status": "claim_type_selected"}

    def checklist(self, question):
        if self.claim_type is None:
            return {"status": "needs_claim_type"}
        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > 1000
        ):
            return {"status": "invalid_question"}
        try:
            result = self.crew_factory(self.claim_type).kickoff(
                inputs={"question": question}
            )
            return inspect_result(result, self.claim_type)
        except Exception:
            # Do not send provider/tool exception text into the conversation.
            return {"status": "incomplete", "reason": "research_unavailable"}
