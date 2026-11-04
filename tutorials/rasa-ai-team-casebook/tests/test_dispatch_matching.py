import itertools
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dispatch_matching import greedy, complete, JOBS, TECHNICIANS, COSTS, demo


class Dispatch(unittest.TestCase):
    def test_every_greedy_assignment_is_eligible_but_one_job_is_lost(self):
        chosen = greedy(JOBS, TECHNICIANS, COSTS)
        self.assertEqual(chosen, [('general', 'specialist', 1)])
        self.assertTrue(all((job, tech) in COSTS for job, tech, _ in chosen))

    def test_all_input_orders_produce_same_complete_assignment(self):
        expected = [('general', 'generalist', 2), ('specialist-only', 'specialist', 2)]
        for jobs in itertools.permutations(JOBS):
            for techs in itertools.permutations(TECHNICIANS):
                self.assertEqual(complete(jobs, techs, COSTS), expected)
        self.assertEqual(demo()['greedy_unserved_orders'], 2)

    def test_coverage_precedes_cost(self):
        costs = {('a', 'x'): 0, ('a', 'y'): 100, ('b', 'x'): 100}
        self.assertEqual(len(complete(['a', 'b'], ['x', 'y'], costs)), 2)

    def test_cost_breaks_equal_coverage(self):
        costs = {('a', 'x'): 5, ('a', 'y'): 1}
        self.assertEqual(complete(['a'], ['x', 'y'], costs), [('a', 'y', 1)])

    def test_tie_break_is_stable_and_capacity_is_one(self):
        costs = {(j,t): 1 for j in ['a','b'] for t in ['x','y']}
        self.assertEqual(complete(['b','a'], ['y','x'], costs), [('a','x',1),('b','y',1)])

    def test_unserviceable_job_does_not_get_invented_edge(self):
        self.assertEqual(complete(['a'], ['x'], {}), [])

    def test_invalid_graph_and_unbounded_search_are_rejected(self):
        for jobs, techs, costs in [(['a','a'],['x'],{}), (['a'],['x'],{('a','x'):-1}),
                                   (['a'],['x'],{('a','z'):1}), ([str(i) for i in range(9)],[],{})]:
            with self.assertRaises(ValueError): complete(jobs, techs, costs)


if __name__ == '__main__': unittest.main()
