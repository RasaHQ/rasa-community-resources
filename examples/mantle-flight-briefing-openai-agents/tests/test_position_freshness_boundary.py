"""Installed Core's position age boundary, with injected HTTP only."""
from datetime import datetime, timezone
import unittest

import httpx
from zeo_core.integrations.briefing_sources import PublicSourceHTTP, StatedDestination
from zeo_core.integrations.briefing_sources.flight import flight


class PositionFreshnessBoundary(unittest.TestCase):
    def test_120_second_position_is_available_but_121_is_unavailable(self):
        now = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
        for age in (120, 121):
            with self.subTest(position_age_seconds=age):
                requests = []

                def handler(request):
                    requests.append(request)
                    self.assertEqual(request.url.host, 'api.adsb.lol')
                    if request.method == 'GET':
                        self.assertTrue(request.url.path.startswith('/v2/callsign/'))
                        return httpx.Response(200, json={'now': now.timestamp(), 'ac': [{
                            'flight': 'DLH400', 'lat': 40.8, 'lon': -73.8, 'gs': 350,
                            'seen_pos': age, 'alt_baro': 25000}]})
                    self.assertEqual(request.url.path, '/api/0/routeset')
                    return httpx.Response(200, json=[{'callsign': 'DLH400', 'plausible': True,
                        '_airports': [{'icao': 'EDDF', 'lat': 50.03, 'lon': 8.57},
                                      {'icao': 'KJFK', 'lat': 40.64, 'lon': -73.78}]}])

                source = PublicSourceHTTP(transport=httpx.MockTransport(handler), clock=lambda: now)
                try:
                    result = flight(source, 'DLH400', fetched_at=now,
                        stated_destination=StatedDestination('KJFK', 40.64, -73.78))
                    self.assertEqual(result.reference.error is None, age == 120)
                    self.assertEqual(len(requests), 2 if age == 120 else 1)
                finally:
                    source.close()


if __name__ == '__main__':
    unittest.main()
