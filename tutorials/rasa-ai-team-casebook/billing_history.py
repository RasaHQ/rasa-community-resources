"""Compare two revision filters and separate-source reports on an invented trace.

No service, Rasa runtime, model, payment, or legal policy is exercised.
The teaching contract makes each (source, revision) immutable.
"""
from itertools import permutations
import json
from billing_reconciliation import STATES, Observation, Reconciliation, fixture


class LatestFirst(Reconciliation):
    """Plausible optimization: skip obsolete observations before validation.

    Equal current revisions still use the original contradiction check. The
    optimization loses contradictions between two already obsolete revisions.
    """

    def receive(self, observation):
        # Keep account/source validation even on the fast path. Its omission
        # would be another defect and would confound this comparison.
        if (observation.account, observation.policy) != (self.account, self.policy):
            raise ValueError("observation belongs to a different account or policy")
        if observation.source not in STATES:
            raise ValueError("unknown source")
        if type(observation.revision) is not int or observation.revision < 1:
            raise ValueError("revision must be a positive integer")
        if observation.state not in STATES[observation.source]:
            raise ValueError("state is invalid for this source")
        old = self.current.get(observation.source)
        if old and observation.revision < old.revision:
            return "older"
        return super().receive(observation)


def separate_sources(reducer):
    """Quarantine a conflicted source, without promoting a joined policy claim.

    These are fixture observations, not authenticated/current service answers.
    Never infer one source's state from another source's successful result.
    """
    reports = {}
    for source in ("invoice", "payment", "policy"):
        observation = reducer.current.get(source)
        valid = observation is not None and source not in reducer.conflicts
        reports[source] = {
            "status": "observed" if valid else "investigate",
            "state": observation.state if valid else "unknown",
        }
    return reports


def old_conflict():
    return Observation("account-1", "policy-1", "policy", 5, "active")


def minimal_trace():
    # Revision 6 arrives before the contradictory pair of revision 5 replies.
    return [fixture()[-1], fixture()[-2], old_conflict()]


def demonstrate():
    latest_missed = strict_detected = orders = 0
    for delivery in permutations([*fixture(), old_conflict()]):
        latest = LatestFirst("account-1", "policy-1")
        strict = Reconciliation("account-1", "policy-1")
        for event in delivery:
            latest.receive(event)
            strict.receive(event)
        latest_missed += "policy" not in latest.conflicts
        strict_detected += "policy" in strict.conflicts
        orders += 1
    strict = Reconciliation("account-1", "policy-1")
    for event in [*fixture(), old_conflict()]:
        strict.receive(event)
    before = strict.report()
    # A later consistent-looking revision cannot certify an investigation or
    # silently revoke the evidence that a supposedly immutable key disagreed.
    strict.receive(Observation("account-1", "policy-1", "policy", 7, "active"))
    after = strict.report()
    return {
        "kind": "authored_synthetic_immutable_revision_contract",
        "delivery_orders": orders,
        "latest_first_missed_old_conflict": latest_missed,
        "retained_history_detected_old_conflict": strict_detected,
        "minimal_policy_trace": [
            {"revision": event.revision, "state": event.state}
            for event in minimal_trace()
        ],
        "whole_report_after_conflict": {
            key: before[key] for key in ("status", "invoice_state", "payment_state", "policy_state")
        },
        "whole_report_after_revision_7": {
            key: after[key] for key in ("status", "invoice_state", "payment_state", "policy_state")
        },
        "separate_source_reports": separate_sources(strict),
        "model_calls": 0,
        "service_calls": 0,
        "payment_actions": 0,
    }


if __name__ == "__main__":
    print(json.dumps(demonstrate(), indent=2))
