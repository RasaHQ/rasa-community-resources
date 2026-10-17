"""Constructed application-policy exercise, not a Mantle confirmation adapter.

An authenticated application's confirmation screen supplies proposal_id and
decision. Neither is a model tool argument. This in-memory, single-process
fixture has no persistence, expiry, concurrency or transport authentication;
it is not a deployable approval service. The existing skill is unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from lib import recovery


class ReleaseReview:
    def __init__(self, service: recovery.Disruption, passenger_id: str):
        self.service = service
        self.passenger_id = passenger_id
        self.pending = None
        self.completed = {}
        self.sequence = 0

    def propose(self, hold_id: str) -> dict:
        hold = recovery.check_hold(self.service, self.passenger_id, hold_id)
        if hold['status'] != 'active':
            return hold
        # A correction retires the old question, not merely its display text.
        if self.pending:
            self.completed[self.pending['proposal_id']] = {
                'status': 'superseded', 'hold_id': self.pending['hold_id']}
        self.sequence += 1
        self.pending = {'status': 'awaiting_application_decision',
                        'proposal_id': f'release-{self.sequence}',
                        'hold_id': hold['hold_id'],
                        'question': f"Give up hold {hold['hold_id']}?"}
        return deepcopy(self.pending)

    def decide(self, proposal_id: str, decision: str) -> dict:
        if proposal_id in self.completed:
            return {**deepcopy(self.completed[proposal_id]), 'replay': True}
        if not self.pending or proposal_id != self.pending['proposal_id']:
            return {'status': 'blocked', 'reason': 'no_matching_question'}
        if decision not in ('accept', 'decline'):
            return {'status': 'blocked', 'reason': 'invalid_decision'}
        hold_id = self.pending['hold_id']
        if decision == 'decline':
            result = {'status': 'declined', 'hold_id': hold_id}
        else:
            # Ownership and current state still belong to the actual service.
            result = recovery.release_hold(self.service, self.passenger_id, hold_id)
        self.completed[proposal_id] = deepcopy(result)
        self.pending = None
        return result


class UnboundAnswerControl(ReleaseReview):
    """Deliberate mutation: apply an answer to whichever question is current.

    This is a constructed control, not the historical model's implementation
    or a model of natural-language understanding. Everything else uses the
    same controller and real fixture service.
    """
    def decide(self, proposal_id: str, decision: str) -> dict:
        if self.pending:
            proposal_id = self.pending['proposal_id']
        return super().decide(proposal_id, decision)
