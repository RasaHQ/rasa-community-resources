"""Exact payload equality can miss a wrong account when fixtures share rows.

Two scripted application controls; no live model or population score.
"""
import json
from typesafe_sdk import RetryPolicy, TypeSafeClient
from .accounts import Accounts
from .scripted import scripted_transport
from .selector import MODEL, Selector

EXPECTED_ACCOUNT = 'A-CURRENT'
EXPECTED_TRANSACTIONS = [{'reference': 'DEMO-101', 'merchant': 'Aster Reading',
                          'currency': 'GBP', 'amount': '-42.18'}]
EXPECTED_CONTROLS = {'current', 'wrong_eligible'}


def capture_controls():
    records = []
    for name, choice in [('current', 'A-CURRENT'), ('wrong_eligible', 'A-SAVINGS')]:
        accounts = Accounts()
        transport, calls = scripted_transport(choice)
        with TypeSafeClient(api_key='scripted-local-test', base_url='https://scripted.invalid',
                            model=MODEL, transport=transport, retry=RetryPolicy(max_retries=0)) as client:
            result = Selector(client, accounts).select('demo-a', 'Show my current account transactions')
        records.append({'case': name, 'requested_account': EXPECTED_ACCOUNT,
                        'actual_account': result['account'], 'status': result['status'],
                        'transactions': result['transactions'], 'account_reads': list(accounts.reads),
                        'scripted_sdk_requests': len(calls), 'external_provider_requests': 0})
    return records


def score(records):
    if len(records) != 2 or {r['case'] for r in records} != EXPECTED_CONTROLS:
        raise ValueError('Score exactly the two distinct declared controls')
    cases = []
    for record in records:
        payload_matches = (record['status'] == 'transactions' and
                           record['transactions'] == EXPECTED_TRANSACTIONS)
        identity_matches = (record['actual_account'] == EXPECTED_ACCOUNT and
                            record['account_reads'] == [EXPECTED_ACCOUNT])
        cases.append({**record, 'payload_matches': payload_matches,
                      'account_bound_matches': payload_matches and identity_matches})
    return {'cases': cases, 'total': len(cases),
            'payload_matches': sum(r['payload_matches'] for r in cases),
            'account_bound_matches': sum(r['account_bound_matches'] for r in cases),
            'payload_only_decision': 'APPROVE' if all(r['payload_matches'] for r in cases) else 'REJECT',
            'account_bound_decision': 'APPROVE' if all(r['account_bound_matches'] for r in cases) else 'REJECT',
            'external_provider_requests': sum(r['external_provider_requests'] for r in cases)}


def main():
    result = score(capture_controls())
    for case in result['cases']:
        print(f"{case['case']}: requested={case['requested_account']}; actual={case['actual_account']}; payload_matches={str(case['payload_matches']).lower()}; account_bound_matches={str(case['account_bound_matches']).lower()}")
    print('identical_transaction_payloads: ' + str(result['cases'][0]['transactions'] == result['cases'][1]['transactions']).lower())
    print(f"exact_payload_checks: {result['payload_matches']}/{result['total']}")
    print(f"account_bound_checks: {result['account_bound_matches']}/{result['total']}")
    for key in ['payload_only_decision', 'account_bound_decision', 'external_provider_requests']:
        print(f"{key}: {result[key]}")


if __name__ == '__main__':
    main()
