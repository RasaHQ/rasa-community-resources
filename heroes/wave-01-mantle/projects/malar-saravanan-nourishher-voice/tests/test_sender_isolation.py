"""Exact sender isolation and refusal controls; stdlib only, no SDK or network."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from lib import store


class SenderIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old = store.DATA_DIR
        store.DATA_DIR = Path(self.tmp.name)
        self.addCleanup(setattr, store, 'DATA_DIR', self.old)

    def test_punctuation_long_prefix_and_exact_whitespace_identities_stay_distinct(self):
        pairs = [('a.b', 'a_b'), ('x' * 128 + 'a', 'x' * 128 + 'b'),
                 ('alice', ' alice'), ('é', 'e\u0301')]
        for first, second in pairs:
            with self.subTest(first=first, second=second):
                store.set_profile_field(first, 'name', 'first')
                store.set_profile_field(second, 'name', 'second')
                store.append_log(first, {'kind': 'meal', 'description': 'first'})
                store.append_log(second, {'kind': 'meal', 'description': 'second'})
                store.save_plan(first, '2026-11-11', {'name': 'first'})
                store.save_plan(second, '2026-11-11', {'name': 'second'})
                self.assertEqual(store.load_profile(first)['name'], 'first')
                self.assertEqual(store.load_profile(second)['name'], 'second')
                self.assertEqual(store.read_log(first)[0]['description'], 'first')
                self.assertEqual(store.read_log(second)[0]['description'], 'second')
                self.assertEqual(store.get_plan(first, '2026-11-11')['name'], 'first')
                self.assertEqual(store.get_plan(second, '2026-11-11')['name'], 'second')

    def test_missing_identity_cannot_read_or_mutate_any_persistent_surface(self):
        store.set_profile_field('default', 'name', 'literal sender')
        before = {p.relative_to(store.DATA_DIR): p.read_bytes() for p in store.DATA_DIR.rglob('*') if p.is_file()}
        for missing in (None, '', '  ', 0):
            operations = [lambda: store.load_profile(missing),
                          lambda: store.set_profile_field(missing, 'name', 'bad'),
                          lambda: store.delete_profile_field(missing, 'name'),
                          lambda: store.append_log(missing, {'kind': 'meal'}),
                          lambda: store.read_log(missing),
                          lambda: store.save_plan(missing, '2026-11-11', {}),
                          lambda: store.get_plan(missing, '2026-11-11')]
            for operation in operations:
                with self.assertRaises(ValueError):
                    operation()
        after = {p.relative_to(store.DATA_DIR): p.read_bytes() for p in store.DATA_DIR.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        with self.assertRaises(ValueError):
            store.user_id_from_context(None)
        self.assertEqual(store.load_profile('default')['name'], 'literal sender')

    def test_legacy_records_are_never_inferred_imported_or_removed(self):
        legacy = store.DATA_DIR / 'profiles/a_b.json'
        legacy.parent.mkdir()
        legacy.write_text(json.dumps({'name': 'ambiguous legacy owner'}))
        original = legacy.read_bytes()
        for sender in ('a.b', 'a_b'):
            self.assertEqual(store.load_profile(sender), {})
            store.set_profile_field(sender, 'name', sender)
        self.assertEqual(legacy.read_bytes(), original)
        self.assertTrue((store.DATA_DIR / 'senders-v2').is_dir())


if __name__ == '__main__':
    unittest.main()
