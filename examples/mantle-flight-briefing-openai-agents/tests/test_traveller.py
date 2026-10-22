"""Ordinary traveller answers become fixed, cited and timezone-aware inputs."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from briefing.traveller import (
    TravellerQuestion, airport_row, destination_hint, flight_number,
    journey, meeting_time, reference, transfer_time,
)

NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


class TravellerControls(unittest.TestCase):
    def test_airport_city_and_airline_words_are_resolved_in_code(self):
        self.assertEqual(destination_hint('I am heading to JFK'), 'KJFK')
        self.assertEqual(destination_hint('New York'), 'New York')
        self.assertEqual(destination_hint('Newark'), 'KEWR')
        self.assertEqual(flight_number('Lufthansa 400'), 'DLH400')
        self.assertEqual(flight_number('LH400'), 'DLH400')
        self.assertEqual(flight_number('United flight 57'), 'UAL57')
        self.assertIsNone(flight_number('my meeting is at 6 pm'))
        self.assertIsNone(destination_hint('https://evil.invalid/'))
        self.assertEqual(len(reference()['airports']), 12)
        for airport in reference()['airports']:
            self.assertEqual(airport['time_zone_source'], 'https://www.iana.org/time-zones')
            self.assertTrue(airport['transfer_default']['transport_source'].startswith('https://'))
            self.assertEqual(airport['transfer_default']['kind'], 'assumption')

    def test_tomorrow_at_six_uses_destination_local_day_and_dst_rules(self):
        airport = airport_row('JFK')
        self.assertEqual(meeting_time('the 6 pm meeting tomorrow', airport, NOW), '2026-10-23T18:00:00-04:00')
        before_local_midnight = datetime(2026, 10, 22, 1, tzinfo=timezone.utc)
        self.assertEqual(meeting_time('tomorrow at 6 pm', airport, before_local_midnight), '2026-10-22T18:00:00-04:00')
        self.assertEqual(meeting_time('today at 18:00', airport, NOW), '2026-10-22T18:00:00-04:00')
        self.assertIsNone(meeting_time('2026-11-01 at 1:30 am', airport, NOW))
        self.assertIsNone(meeting_time('2027-03-14 at 2:30 am', airport, NOW))
        self.assertIsNone(meeting_time('tomorrow morning', airport, NOW))
        self.assertIsNone(meeting_time('6 pm', airport, NOW))

    def test_default_is_labelled_and_user_can_change_it_without_losing_flight(self):
        value = journey('Lufthansa 400 to JFK, the 6 pm meeting tomorrow', now=NOW)
        self.assertEqual(value['callsign'], 'DLH400')
        self.assertEqual(value['destination'], 'KJFK')
        self.assertEqual(value['meeting_time'], '2026-10-23T18:00:00-04:00')
        self.assertEqual(value['transfer_minutes'], 90)
        self.assertTrue(value['transfer_assumed'])
        changed = journey('Allow an hour to get into town', value, now=NOW)
        self.assertEqual(changed['callsign'], value['callsign'])
        self.assertEqual(changed['meeting_time'], value['meeting_time'])
        self.assertEqual(changed['transfer_minutes'], 60)
        self.assertFalse(changed['transfer_assumed'])
        self.assertEqual(transfer_time('allow 45 minutes for the taxi'), 45)

    def test_missing_or_ambiguous_details_get_ordinary_questions(self):
        for text in ['hello', 'New York', 'Lufthansa 400 to JFK', 'Lufthansa 400 to London']:
            with self.subTest(text=text), self.assertRaises(TravellerQuestion) as caught:
                journey(text, now=NOW)
            question = caught.exception.question.lower()
            for technical in ('callsign', 'ads-b', 'icao', 'iso', 'timezone', 'transfer minutes'):
                self.assertNotIn(technical, question)
        with self.assertRaises(TravellerQuestion) as caught:
            journey('Lufthansa 400 to JFK', now=NOW)
        value = journey('tomorrow at 6 pm', caught.exception.inputs, now=NOW)
        self.assertEqual(value['callsign'], 'DLH400')
        self.assertEqual(value['meeting_time'], '2026-10-23T18:00:00-04:00')

    def test_origin_never_wins_over_destination_and_alternatives_need_a_choice(self):
        for route in ['from LHR to JFK', 'to JFK from LHR']:
            value = journey('Lufthansa 400 ' + route + ', meeting tomorrow at 6 pm', now=NOW)
            self.assertEqual(value['destination'], 'KJFK')
            self.assertEqual(value['meeting_time'], '2026-10-23T18:00:00-04:00')
        with self.assertRaises(TravellerQuestion) as caught:
            journey('Lufthansa 400 to JFK or Newark, meeting tomorrow at 6 pm', now=NOW)
        self.assertEqual(caught.exception.field, 'destination')
        self.assertNotIn('destination', caught.exception.inputs)
        self.assertEqual(caught.exception.inputs['callsign'], 'DLH400')

    def test_ambiguous_meeting_revision_clears_old_time_and_resumes_same_flight(self):
        original = journey('Lufthansa 400 to JFK, meeting tomorrow at 6 pm', now=NOW)
        for change in ['move my meeting to tomorrow morning',
                       'move my meeting to 2026-11-01 at 1:30 am',
                       'move my meeting to 2027-03-14 at 2:30 am',
                       'move my meeting to today at 6 am']:
            with self.subTest(change=change), self.assertRaises(TravellerQuestion) as caught:
                journey(change, original, now=NOW)
            missing = caught.exception
            self.assertEqual(missing.field, 'meeting_time')
            self.assertNotIn('meeting_time', missing.inputs)
            self.assertEqual(missing.inputs['callsign'], 'DLH400')
            self.assertEqual(missing.inputs['destination'], 'KJFK')
            repaired = journey('tomorrow at 9 am', missing.inputs, now=NOW)
            self.assertEqual(repaired['meeting_time'], '2026-10-23T09:00:00-04:00')


if __name__ == '__main__':
    unittest.main()
