"""Public static route provenance and refusal controls; no provider or model."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from briefing.published_routes import (
    DATA, PINNED_SHA256, SOURCE_COMMIT, ROUTE_DATE, load_routes, _parse_routes,
)


class PublishedRouteControls(unittest.TestCase):
    def test_pinned_subset_is_small_dated_immutable_and_only_nyc(self):
        routes = load_routes()
        self.assertEqual(len(routes.rows), 1762)
        self.assertLessEqual(DATA.stat().st_size, 200000)
        self.assertEqual(hashlib.sha256(DATA.read_bytes()).hexdigest(), PINNED_SHA256)
        self.assertEqual(routes.source_date, ROUTE_DATE)
        self.assertEqual(routes.source_commit, SOURCE_COMMIT)
        self.assertIn('not all flights', routes.coverage)
        self.assertEqual({r.destination for r in routes.rows}, {'KJFK', 'KEWR', 'KLGA'})
        self.assertEqual(len({r.callsign for r in routes.rows}), len(routes.rows))
        with self.assertRaises(AttributeError):
            routes.rows[0].airline = 'invented airline'

    def test_manifest_binds_all_original_sources_and_subset(self):
        source = json.loads((DATA.parent / 'nyc-routes-SOURCE.json').read_text())
        self.assertEqual(source['commit'], SOURCE_COMMIT)
        self.assertEqual(source['license'], 'CC0-1.0')
        self.assertEqual(source['subset']['sha256'], PINNED_SHA256)
        self.assertEqual(source['subset']['bytes'], DATA.stat().st_size)
        self.assertEqual(len(source['carrierSubset']), 16)
        for original in source['inputs']:
            self.assertRegex(original['sha256'], r'^[a-f0-9]{64}$')
            self.assertTrue(original['path'] == 'LICENSE' or original['path'].startswith(('routes/schema-01/', 'airlines/schema-01/')))
            self.assertNotIn('aircraft/', original['path'])

    def test_changed_oversized_missing_and_malformed_tables_fail_without_echo(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / 'CANARY-private-input'
            for raw in (b'CANARY-private-input', DATA.read_bytes() + b' ', b'x' * 200001):
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'could not be verified') as caught:
                    load_routes(path)
                self.assertNotIn('CANARY', str(caught.exception))
                self.assertNotIn(str(path), str(caught.exception))
            path.unlink()
            with self.assertRaises(ValueError):
                load_routes(path)

    def test_schema_duplicate_callsign_wrong_destination_and_hostile_text_refuse(self):
        baseline = {'schema': 'rasa.nyc-published-routes/v1',
                    'columns': ['callsign', 'airline', 'origin', 'destination'],
                    'routes': [['TST1', 'Test Airline', 'EGLL', 'KJFK']]}
        for row in (['TST1', '<script>CANARY</script>', 'EGLL', 'KJFK'],
                    ['TST1', 'Test Airline', 'EGLL', 'EDDF'],
                    ['TST1', 'Test Airline', 'KJFK', 'KJFK'],
                    ['https://evil.invalid', 'Test Airline', 'EGLL', 'KJFK']):
            value = {**baseline, 'routes': [row]}
            with self.assertRaises(ValueError):
                _parse_routes(json.dumps(value))
        with self.assertRaises(ValueError):
            _parse_routes(json.dumps({**baseline, 'routes': baseline['routes'] * 2}))
        with self.assertRaises(ValueError):
            _parse_routes('{"schema":1,"schema":2}')
        self.assertEqual(_parse_routes(json.dumps(baseline))[0].airline, 'Test Airline')


if __name__ == '__main__':
    unittest.main()
