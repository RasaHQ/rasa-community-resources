"""Bounded, invented dispatch costs: maximize served jobs before minimizing travel."""
import itertools
import json


def validate(jobs, technicians, costs):
    for names in (jobs, technicians):
        if len(names) != len(set(names)) or any(not isinstance(x, str) or not x for x in names):
            raise ValueError('Unique nonempty identities required')
    if len(jobs) > 8 or len(technicians) > 8:
        raise ValueError('Exhaustive teaching search is limited to eight jobs and technicians')
    for (job, tech), cost in costs.items():
        if job not in jobs or tech not in technicians or type(cost) is not int or cost < 0:
            raise ValueError('Every eligible edge needs known identities and nonnegative integer cost')


def greedy(jobs, technicians, costs):
    validate(jobs, technicians, costs)
    used, assignments = set(), []
    for job in jobs:
        choices = [(costs[(job, tech)], tech) for tech in technicians
                   if tech not in used and (job, tech) in costs]
        if choices:
            cost, tech = min(choices)
            used.add(tech); assignments.append((job, tech, cost))
    return assignments


def complete(jobs, technicians, costs):
    validate(jobs, technicians, costs)
    jobs, technicians = sorted(jobs), sorted(technicians)
    def candidates(index, used, chosen):
        if index == len(jobs):
            yield tuple(chosen)
            return
        job = jobs[index]
        yield from candidates(index + 1, used, chosen)
        for tech in technicians:
            if tech not in used and (job, tech) in costs:
                yield from candidates(index + 1, used | {tech}, chosen + [(job, tech, costs[(job, tech)])])
    # Tie-break by stable identities so input order does not choose a person.
    return list(min(candidates(0, set(), []), key=lambda a: (-len(a), sum(x[2] for x in a), a)))


JOBS = ['general', 'specialist-only']
TECHNICIANS = ['specialist', 'generalist']
COSTS = {('general', 'specialist'): 1, ('general', 'generalist'): 2,
         ('specialist-only', 'specialist'): 2}


def demo():
    comparisons = []
    for jobs in itertools.permutations(JOBS):
        for techs in itertools.permutations(TECHNICIANS):
            comparisons.append({'job_order': jobs, 'technician_order': techs,
                                'greedy': greedy(jobs, techs, COSTS),
                                'complete': complete(jobs, techs, COSTS)})
    return {'kind': 'invented_eligibility_and_costs', 'comparisons': comparisons,
            'orders': len(comparisons),
            'greedy_unserved_orders': sum(len(c['greedy']) < 2 for c in comparisons),
            'complete_two_job_orders': sum(len(c['complete']) == 2 for c in comparisons)}


if __name__ == '__main__': print(json.dumps(demo(), indent=2, sort_keys=True))
