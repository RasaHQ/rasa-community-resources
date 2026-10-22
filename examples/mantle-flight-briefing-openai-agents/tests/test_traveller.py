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
    def test_uncovered_search_never_reasks_flight_number_or_invents_no_flights(self):
        from briefing.traveller import discover, discovery_notice
        class NoNetwork:
            def find_flights(self, *args, **kwargs):
                raise AssertionError('unsupported destination must not invent covered routes')
        for city in ('London', 'Reykjavik'):
            result = discover(NoNetwork(), 'flight to ' + city + ' tonight')
            self.assertEqual(result['status'], 'unsupported_destination')
            notice = discovery_notice(result)
            self.assertIn(city, notice)
            self.assertIn('New York only', notice)
            self.assertIn('does not mean there are no flights', notice)
            self.assertNotIn('Do you know', notice)
            self.assertEqual(result['candidates'], [])

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
        with self.assertRaises(TravellerQuestion) as opening:
            journey('hello', now=NOW)
        greeting = opening.exception.question
        self.assertIn('where it is, the weather when you land', greeting)
        self.assertIn('whether you\'ll make your meeting, and the exchange rate', greeting)
        self.assertTrue(greeting.endswith('Where are you heading?'))
        self.assertLessEqual(len(greeting), 200)
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

    def test_travel_allowance_never_reads_half_or_decimal_as_a_larger_integer(self):
        original = journey('Lufthansa 400 to JFK, meeting tomorrow at 6 pm', now=NOW)
        for words, minutes in [('half an hour', 30), ('an hour', 60),
                               ('1 hour and 30 minutes', 90), ('an hour and a half', 90),
                               ('45 minutes', 45)]:
            changed = journey('allow ' + words + ' to get into town', original, now=NOW)
            self.assertEqual(changed['transfer_minutes'], minutes)
            self.assertEqual(changed['callsign'], original['callsign'])
            self.assertEqual(changed['meeting_time'], original['meeting_time'])
        for words in ['1.5 hours', '1,5 hours', '-30 minutes', '25 hours']:
            with self.subTest(words=words), self.assertRaises(TravellerQuestion) as caught:
                journey('allow ' + words + ' to get into town', original, now=NOW)
            self.assertEqual(caught.exception.field, 'transfer_minutes')
            self.assertNotIn('transfer_minutes', caught.exception.inputs)

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
