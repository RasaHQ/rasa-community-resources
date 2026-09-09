import hashlib
import io
import unittest
import zipfile
from index import candidates, discover, inspect_release


def release(version, **kwargs):
    return {'filename': f'rasa_pro-{version}-py3-none-any.whl', 'yanked': False, 'requires_python': '>=3.11,<3.14', **kwargs}


class ReleaseTests(unittest.TestCase):
    def test_pep440_sort_prerelease_final_post_and_new_major(self):
        versions = ['3.20.0.dev9', '3.20.0rc2', '3.20.0rc10', '3.20.0', '3.20.0.post1', '3.21.0a1', '4.0.0.dev1']
        result = candidates({'releases': {v: [release(v)] for v in reversed(versions)}})
        self.assertEqual(result, versions)

    def test_empty_yanked_sdist_and_incompatible_releases_cannot_win(self):
        self.assertEqual(candidates({'releases': {
            '3.20.0.dev9': [release('3.20.0.dev9')],
            '4.0.0': [], '4.0.1': [release('4.0.1', yanked=True)],
            '5.0.0': [release('5.0.0', requires_python='>=3.14')],
            '6.0.0': [release('6.0.0', filename='rasa.tar.gz')],
            'invalid': [release('invalid')],
        }}), ['3.20.0.dev9'])

    def test_newest_incompatible_engine_is_reported_without_fallback(self):
        data = {'releases': {v: [release(v)] for v in ['3.20.0.dev9', '4.0.0']}}
        report = discover(data, lambda v: {'version': v, 'mantlePresent': v != '4.0.0'})
        self.assertEqual(report['selected']['version'], '4.0.0')
        self.assertFalse(report['selected']['mantlePresent'])

    def test_wheel_hash_and_actual_module_membership(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z: z.writestr('rasa/mantle/__init__.py', '')
        raw = buf.getvalue()
        wheel = {**release('3.20.0.dev9'), 'size': len(raw), 'url': 'https://files.pythonhosted.org/test.whl', 'digests': {'sha256': hashlib.sha256(raw).hexdigest()}, 'upload_time_iso_8601': '2026-09-08T00:00:00Z'}
        self.assertTrue(inspect_release('3.20.0.dev9', {'urls': [wheel]}, lambda _: raw)['mantlePresent'])
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            inspect_release('3.20.0.dev9', {'urls': [wheel]}, lambda _: raw + b'changed')
        wheel['url'] = 'https://attacker.invalid/test.whl'
        with self.assertRaisesRegex(ValueError, 'host'):
            inspect_release('3.20.0.dev9', {'urls': [wheel]}, lambda _: raw)


if __name__ == '__main__': unittest.main()
