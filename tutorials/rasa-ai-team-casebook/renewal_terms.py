"""Invented renewal records: completeness and patch semantics are explicit."""
import json

FIELDS = {'deductible', 'limit'}
BASE = {'revision': 'r1', 'terms': {'deductible': 500, 'limit': 10000}}


def naive_merge(previous, offer):
    return {name: offer.get('terms', {}).get(name, previous['terms'][name]) for name in FIELDS}


def resolve(previous, offer):
    if not isinstance(offer, dict) or set(offer) != {'mode', 'base_revision', 'terms'}:
        raise ValueError('Declare mode, base revision and terms')
    if offer['mode'] not in {'snapshot', 'patch'} or offer['base_revision'] != previous['revision']:
        raise ValueError('Unknown mode or stale base revision')
    terms = offer['terms']
    if not isinstance(terms, dict) or set(terms) - FIELDS:
        raise ValueError('Unknown term field')
    if offer['mode'] == 'snapshot' and set(terms) != FIELDS:
        raise ValueError('Incomplete full offer')
    result = {}
    for name in sorted(FIELDS):
        if name not in terms:  # Only explicit patch mode allows omission.
            result[name] = previous['terms'][name]
            continue
        value = terms[name]
        if not isinstance(value, dict) or len(value) != 1:
            raise ValueError('Use a value or an unchanged revision reference')
        if 'unchanged_from' in value:
            if value['unchanged_from'] != previous['revision']:
                raise ValueError('Unchanged term references another revision')
            result[name] = previous['terms'][name]
        elif 'value' in value and type(value['value']) is int and value['value'] >= 0:
            result[name] = value['value']
        else:
            raise ValueError('Missing, null or unknown value is unresolved')
    return result


def demo():
    omitted = {'terms': {'limit': 12000}}
    outcomes = {'naive_omitted_deductible': naive_merge(BASE, omitted)}
    for mode in ['snapshot', 'patch']:
        offer = {'mode': mode, 'base_revision': 'r1', 'terms': {'limit': {'value': 12000}}}
        try: outcomes[mode] = resolve(BASE, offer)
        except ValueError as error: outcomes[mode] = {'unresolved': str(error)}
    outcomes['explicit_unchanged_snapshot'] = resolve(BASE, {
        'mode': 'snapshot', 'base_revision': 'r1',
        'terms': {'limit': {'value': 12000}, 'deductible': {'unchanged_from': 'r1'}}})
    return outcomes


if __name__ == '__main__': print(json.dumps(demo(), indent=2, sort_keys=True))
