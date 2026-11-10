"""Finite synthetic read-only reconciliation; no payment or policy service calls."""
from dataclasses import asdict, dataclass
from itertools import permutations
import json

STATES = {
    "payment": {"pending", "settled"},
    "invoice": {"overdue", "paid"},
    "policy": {"active", "lapsed"},
}


@dataclass(frozen=True)
class Observation:
    account: str
    policy: str
    source: str
    revision: int
    state: str


class Reconciliation:
    """Select revisions within each trusted source, never across sources.

    Revisions and source identity are fixture inputs, not authenticated here.
    An equal-revision contradiction requires investigation, even if later data
    arrives. There is intentionally no automatic conflict-clearing rule.
    """

    def __init__(self, account, policy):
        self.account, self.policy = account, policy
        self.current = {}
        self.conflicts = set()
        self.seen = {}

    def receive(self, observation):
        if (observation.account, observation.policy) != (self.account, self.policy):
            raise ValueError("observation belongs to a different account or policy")
        if observation.source not in STATES:
            raise ValueError("unknown source")
        if type(observation.revision) is not int or observation.revision < 1:
            raise ValueError("revision must be a positive integer")
        if observation.state not in STATES[observation.source]:
            raise ValueError("state is invalid for this source")
        key = (observation.source, observation.revision)
        previous = self.seen.get(key)
        if previous and previous != observation:
            self.conflicts.add(observation.source)
            return "conflict"
        self.seen[key] = observation
        old = self.current.get(observation.source)
        if old and observation.revision <= old.revision:
            return "duplicate" if observation == old else "older"
        self.current[observation.source] = observation
        return "selected"

    def report(self):
        missing = sorted(set(STATES) - self.current.keys())
        # All three observations are required by this teaching contract.
        # Missing or contradictory data never produces a policy status claim.
        ready = not missing and not self.conflicts
        return {
            "status": "ready" if ready else "investigate",
            "policy_state": self.current["policy"].state if ready else "unknown",
            "payment_state": self.current["payment"].state if ready else "unknown",
            "invoice_state": self.current["invoice"].state if ready else "unknown",
            "missing": missing,
            "conflicts": sorted(self.conflicts),
            "selected": {key: asdict(value) for key, value in sorted(self.current.items())},
            "payment_actions": 0,
        }


def fixture():
    """Invented revisions: their numbers cannot be compared across sources."""
    return [
        Observation("account-1", "policy-1", "payment", 40, "pending"),
        Observation("account-1", "policy-1", "payment", 41, "settled"),
        Observation("account-1", "policy-1", "invoice", 90, "overdue"),
        Observation("account-1", "policy-1", "invoice", 91, "paid"),
        Observation("account-1", "policy-1", "policy", 5, "lapsed"),
        Observation("account-1", "policy-1", "policy", 6, "active"),
    ]


def demonstrate():
    runs = wrong_inferred_claims = ready_reports = 0
    for delivery in permutations(fixture()):
        result = Reconciliation("account-1", "policy-1")
        first_invoice = next(event for event in delivery if event.source == "invoice")
        # Deliberately defective comparison, not a discovered production system:
        # freeze the first invoice and infer policy status from its label.
        inferred_policy = "lapsed" if first_invoice.state == "overdue" else "active"
        for event in delivery:
            result.receive(event)
        report = result.report()
        assert (report["policy_state"], report["payment_state"], report["invoice_state"]) == (
            "active", "settled", "paid"
        )
        wrong_inferred_claims += inferred_policy != report["policy_state"]
        ready_reports += report["status"] == "ready"
        runs += 1
    return {"kind": "authored_synthetic_fixture", "delivery_orders": runs,
            "first_invoice_inference_wrong": wrong_inferred_claims,
            "per_source_revision_reports_ready": ready_reports,
            "model_calls": 0, "service_calls": 0, "payment_actions": 0}


if __name__ == "__main__":
    print(json.dumps(demonstrate(), indent=2))
