import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from renewal_terms import BASE, resolve, naive_merge


class Renewal(unittest.TestCase):
    def offer(self, mode='snapshot', **terms):
        return {'mode':mode,'base_revision':'r1','terms':terms}

    def test_fallback_treats_incomplete_full_offer_as_complete(self):
        self.assertEqual(naive_merge(BASE, {'terms':{'limit':12000}}), {'deductible':500,'limit':12000})
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            resolve(BASE,self.offer(limit={'value':12000}))

    def test_explicit_patch_contract_allows_omission(self):
        self.assertEqual(resolve(BASE,self.offer('patch',limit={'value':12000})), {'deductible':500,'limit':12000})

    def test_complete_snapshot_can_bind_unchanged_term_to_revision(self):
        self.assertEqual(resolve(BASE,self.offer(limit={'value':12000},deductible={'unchanged_from':'r1'})), {'deductible':500,'limit':12000})

    def test_null_unknown_and_boolean_are_not_terms(self):
        for value in [None, {}, {'value':None}, {'value':True}, {'unknown':True}, {'value':-1}]:
            with self.assertRaises(ValueError): resolve(BASE,self.offer('patch',deductible=value))

    def test_wrong_revision_cannot_supply_unchanged_terms(self):
        with self.assertRaises(ValueError): resolve(BASE,self.offer('patch',deductible={'unchanged_from':'r0'}))
        offer=self.offer('patch'); offer['base_revision']='r0'
        with self.assertRaises(ValueError): resolve(BASE,offer)

    def test_unknown_mode_field_and_missing_contract_are_rejected(self):
        for offer in [self.offer('guess'),self.offer('patch',premium={'value':100}),{'terms':{}}]:
            with self.assertRaises(ValueError): resolve(BASE,offer)

    def test_zero_value_is_explicit_not_missing(self):
        self.assertEqual(resolve(BASE,self.offer('patch',deductible={'value':0}))['deductible'],0)


if __name__ == '__main__': unittest.main()
