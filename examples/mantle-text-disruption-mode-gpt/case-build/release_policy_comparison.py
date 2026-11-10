"""Print constructed application-policy outcomes, not saved conversation data."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import recovery
from exercises.release_decision import ReleaseReview, UnboundAnswerControl

PASSENGER = 'HT-PAX-3308'
MIAMI = 'HT-HLD-4K7M'


def compare() -> list[dict]:
    rows = []
    for route in ('direct_service', 'application_decision'):
        service = recovery.Disruption()
        before = dict(service.inventory)
        review = ReleaseReview(service, PASSENGER)
        question = review.propose(MIAMI)
        # Construct the same refused application decision. In the direct
        # control, deliberately call the old service anyway to show whether
        # service ownership checks alone enforce that decision.
        if route == 'direct_service':
            result = recovery.release_hold(service, PASSENGER, MIAMI)
        else:
            result = review.decide(question['proposal_id'], 'decline')
        rows.append({'case': 'refusal', 'route': route,
                     'result': result['status'],
                     'miami_hold': recovery.check_hold(service, PASSENGER, MIAMI)['status'],
                     'seats_returned': sum(service.inventory.values()) - sum(before.values())})

    for route, controller in [('unbound_answer_control', UnboundAnswerControl),
                              ('application_decision', ReleaseReview)]:
        service = recovery.Disruption()
        review = controller(service, PASSENGER)
        recovery.find_recovery_options(service, PASSENGER, 'Chicago')
        recovery.select_option(service, PASSENGER, 'OPT-ORD-315')
        held = recovery.hold_recovery_option(service, PASSENGER, 'OPT-ORD-315',
                                            'OPT-ORD-315', 'constructed-comparison')
        assert held['status'] == 'held'
        chicago = held['hold_id']
        old = review.propose(MIAMI)
        new = review.propose(chicago)
        for case, proposal in [('old_answer_after_correction', old),
                               ('current_answer', new), ('replayed_current_answer', new)]:
            before = dict(service.inventory)
            result = review.decide(proposal['proposal_id'], 'accept')
            rows.append({'case': case, 'route': route,
                         'result': result['status'], 'replay': result.get('replay', False),
                         'miami_hold': recovery.check_hold(service, PASSENGER, MIAMI)['status'],
                         'chicago_hold': recovery.check_hold(service, PASSENGER, chicago)['status'],
                         'seats_returned': sum(service.inventory.values()) - sum(before.values())})
    return rows


if __name__ == '__main__':
    print(json.dumps({'kind': 'constructed-application-policy-comparison',
                      'native_mantle_confirmation_tested': False,
                      'rows': compare()}, indent=2))
