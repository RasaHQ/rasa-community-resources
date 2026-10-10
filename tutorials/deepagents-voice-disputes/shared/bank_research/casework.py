"""Synthetic case state. A research result is never authority to submit."""
from dataclasses import dataclass, field
import hashlib
import secrets

TRANSACTIONS = {
    "TX-101": {"owner": "demo-a", "merchant": "PINE*ANNUAL", "amount": "49.00", "currency": "GBP", "date": "2026-10-06"},
    "TX-102": {"owner": "demo-a", "merchant": "RIVER HOTEL", "amount": "149.00", "currency": "GBP", "date": "2026-10-07"},
    "TX-201": {"owner": "demo-b", "merchant": "PINE*ANNUAL", "amount": "49.00", "currency": "GBP", "date": "2026-10-06"},
}


def evidence_for(transaction_id):
    tx = TRANSACTIONS[transaction_id]
    return {
        "transaction": {k: v for k, v in tx.items() if k != "owner"},
        "descriptor": {"text": "PINE*ANNUAL is the descriptor used by the fictional Pine Reading annual membership." if tx["merchant"] == "PINE*ANNUAL" else "No descriptor match is available."},
        "review-policy": {"text": "An unfamiliar descriptor does not establish fraud. Record the customer's account of events for staff review. No refund is decided here."},
    }


@dataclass
class CaseSession:
    """In-memory demo only; no durable queue, production auth or customer data."""
    revision: int = 0
    owner: str | None = None
    selected: str | None = None
    proposal: dict | None = None
    submitted: dict = field(default_factory=dict)

    def verify_demo(self, code):
        # Published fixture codes are NOT authentication. Never deploy this.
        mapping = {"111111": "demo-a", "222222": "demo-b"}
        found = mapping.get(code)
        if not found or (self.owner and self.owner != found):
            return {"error": "demo_identity_not_selected"}
        self.owner = found
        return {"status": "demo_identity_selected"}

    def select(self, transaction_id):
        # Always invalidate the old proposal, even for a denied correction.
        self.revision += 1
        self.proposal = None
        self.selected = None
        tx = TRANSACTIONS.get(transaction_id)
        if not self.owner or not tx or tx["owner"] != self.owner:
            return {"error": "transaction_unavailable"}
        self.selected = transaction_id
        return {"status": "selected", "transaction_id": transaction_id, **evidence_for(transaction_id)["transaction"]}

    def evidence(self):
        if not self.selected:
            raise ValueError("Select an owned transaction first")
        return evidence_for(self.selected)

    def prepare(self):
        if not self.selected:
            return {"error": "no_selected_transaction"}
        # Repeated requests reuse the proposal until selection changes.
        if not self.proposal:
            tx = evidence_for(self.selected)["transaction"]
            self.proposal = {"proposal_id": secrets.token_hex(8), "transaction_id": self.selected, **tx}
        return {"status": "prepared", **self.proposal}

    def submit(self, proposal_id, merchant, amount, currency, date):
        # Mantle confirmation must have happened BEFORE calling this function.
        # This function verifies binding and idempotency, not spoken consent.
        if not self.proposal or proposal_id != self.proposal["proposal_id"] or self.selected != self.proposal["transaction_id"]:
            return {"error": "proposal_changed_or_missing"}
        if any(self.proposal[key] != value for key, value in (("merchant", merchant), ("amount", amount), ("currency", currency), ("date", date))):
            return {"error": "readback_changed"}
        if proposal_id not in self.submitted:
            reference = "DEMO-" + hashlib.sha256(proposal_id.encode()).hexdigest()[:8].upper()
            self.submitted[proposal_id] = {"status": "demo_recorded", "reference": reference, "transaction_id": self.selected, "next_step": "Staff review; no refund decided. This record disappears when the server stops."}
        return dict(self.submitted[proposal_id])
