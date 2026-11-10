"""Bind a model proposal to its conversation and consume it once."""
from dataclasses import dataclass
from secrets import token_urlsafe


@dataclass(frozen=True)
class Proposal:
    token: str
    owner: str
    snapshot: object
    account: str


class Proposals:
    def __init__(self, selector):
        self.selector = selector
        self.pending = {}

    def propose(self, owner, conversation, message):
        if not isinstance(conversation, str) or not 1 <= len(conversation) <= 128:
            return {"status": "invalid_conversation"}
        # Retire the old proposal before obtaining a new decision, including a
        # failed or clarification decision. Old tokens must never remain usable.
        self.pending.pop(conversation, None)
        snapshot, result = self.selector.decide(owner, message)
        if result["status"] != "account_proposal":
            return result
        if snapshot.revision != self.selector.accounts.revision:
            return {"status": "stale_options"}
        proposal = Proposal(token_urlsafe(24), owner, snapshot, result["account"])
        self.pending[conversation] = proposal
        return {**result, "proposal_token": proposal.token}

    def confirm(self, owner, conversation, token):
        proposal = self.pending.get(conversation)
        if proposal is None or proposal.token != token or proposal.owner != owner:
            return {"status": "proposal_changed"}
        del self.pending[conversation]
        return self.selector.accounts.read(proposal.snapshot, proposal.account)

    def cancel(self, owner, conversation, token):
        proposal = self.pending.get(conversation)
        if proposal is None or proposal.token != token or proposal.owner != owner:
            return {"status": "proposal_changed"}
        del self.pending[conversation]
        return {"status": "proposal_cancelled"}
