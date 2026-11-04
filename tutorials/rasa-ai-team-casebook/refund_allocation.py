"""Invented one-unit line-item refunds using integer largest-remainder allocation."""
import itertools
import json

WEIGHTS = {'A':100, 'B':100, 'C':300}
TOTAL = 303


def allocate(total, weights):
    if type(total) is not int or total < 0 or not isinstance(weights, dict) or not weights:
        raise ValueError('Nonnegative integer total and nonempty item weights required')
    if any(not isinstance(k,str) or not k or type(v) is not int or v <= 0 for k,v in weights.items()):
        raise ValueError('Stable item identities and positive integer weights required')
    denominator = sum(weights.values())
    allocated = {item: total*weight//denominator for item,weight in weights.items()}
    rank = sorted(weights, key=lambda item: (-(total*weights[item] % denominator), item))
    for item in rank[:total-sum(allocated.values())]: allocated[item] += 1
    return allocated


class Refunds:
    def __init__(self, total, weights):
        self.original = allocate(total, weights)
        self.requests = {}
        self.returned = set()

    def refund(self, request, item):
        if not isinstance(request,str) or not request or item not in self.original:
            raise ValueError('Known item and stable refund request required')
        if request in self.requests:
            previous, amount = self.requests[request]
            if previous != item: raise ValueError('Refund identity names another item')
            return amount
        if item in self.returned: raise ValueError('Item already refunded under another request')
        amount = self.original[item]
        self.requests[request] = (item, amount)
        self.returned.add(item)
        return amount


def dynamic_returns(total, weights, order):
    remaining, result = dict(weights), {}
    for item in order:
        amount = allocate(total, remaining)[item]
        result[item] = amount
        total -= amount
        del remaining[item]
    return result


def demo():
    original = allocate(TOTAL, WEIGHTS)
    runs = []
    for order in itertools.permutations(WEIGHTS):
        ledger = Refunds(TOTAL, WEIGHTS)
        fixed = {item:ledger.refund('return-'+item,item) for item in order}
        runs.append({'order':order, 'reallocated':dynamic_returns(TOTAL,WEIGHTS,order), 'original_allocation':fixed})
    return {'kind':'invented_single_unit_line_item_policy','total_minor':TOTAL,'weights':WEIGHTS,
            'original':original,'orders':len(runs),
            'orders_changing_an_item':sum(run['reallocated'] != original for run in runs), 'runs':runs}


if __name__ == '__main__': print(json.dumps(demo(), indent=2, sort_keys=True))
