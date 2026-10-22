"""Traveller words become bounded values in code; models supply no source facts."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

from briefing.published_routes import load_routes

REFERENCE = Path(__file__).with_name('traveller-reference-20261022.json')
REFERENCE_SHA256 = 'a2a034c8770c4bccae8ba1fa71737f16a6ed433280b255b7429c422cf555222a'


class TravellerQuestion(ValueError):
    def __init__(self, field, question, inputs):
        super().__init__('traveller_input_required')
        self.field, self.question, self.inputs = field, question, dict(inputs)


@lru_cache(maxsize=1)
def reference():
    raw = REFERENCE.read_bytes()
    if len(raw) > 200000 or hashlib.sha256(raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError('traveller_reference_unverified')
    data = json.loads(raw)
    if data.get('schema') != 'rasa.traveller-reference/v1':
        raise ValueError('traveller_reference_unverified')
    for airport in data['airports']:
        ZoneInfo(airport['time_zone'])
        if not 0 <= airport['transfer_default']['minutes'] <= 1440:
            raise ValueError('traveller_reference_unverified')
    return data


def normalized(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def airport_row(code):
    found = [a for a in reference()['airports'] if code in (a['ident'], a['iata_code'])]
    if len(found) != 1:
        raise ValueError('unsupported_destination')
    return dict(found[0])


def destination_hint(text):
    value = normalized(text)
    # Airport names/codes take precedence over a metro name in the same answer.
    for airport in reference()['airports']:
        for alias in (airport['ident'], airport['iata_code'], *airport['aliases']):
            if re.search(r'(?<![a-z0-9])' + re.escape(normalized(alias)) + r'(?![a-z0-9])', value):
                return airport['ident']
    for city in sorted({a['city'] for a in reference()['airports']}, key=len, reverse=True):
        if re.search(r'\b' + re.escape(normalized(city)) + r'\b', value):
            return city
    return 'New York' if re.search(r'\bnyc\b', value) else None


def flight_number(text):
    value = normalized(text)
    internal = re.search(r'\bcallsign=([a-z0-9]{2,10})(?=\s|$)', value)
    if internal:
        return internal[1].upper()
    for airline in reference()['airlines']:
        for alias in sorted(airline['aliases'], key=len, reverse=True):
            if not alias:
                continue
            match = re.search(r'(?<![a-z0-9])' + re.escape(normalized(alias)) + r'\s*(?:flight\s*)?([0-9]{1,4}[a-z]{0,2})(?![a-z0-9])', value)
            if match:
                number = match[1].upper().lstrip('0') or '0'
                return airline['icao'] + number
    return None


def flight_name(callsign):
    for airline in reference()['airlines']:
        if callsign.startswith(airline['icao']):
            return airline['name'] + ' ' + (callsign[3:].lstrip('0') or '0')
    return callsign


def _airport_for(hint, callsign, inputs):
    try:
        return airport_row(hint)
    except ValueError:
        pass
    choices = [a for a in reference()['airports'] if a['city'] == hint]
    if len(choices) == 1:
        return dict(choices[0])
    published = next((r for r in load_routes().rows if r.callsign == callsign), None)
    if published and published.destination in {a['ident'] for a in choices}:
        return airport_row(published.destination)
    names = 'Heathrow or Gatwick' if hint == 'London' else 'Kennedy, Newark or LaGuardia'
    raise TravellerQuestion('destination', 'Which airport are you arriving at — ' + names + '?', inputs)


def meeting_time(text, airport, now):
    """Only explicit dates and ordinary clock phrases; DST gaps/folds need a question."""
    zone = ZoneInfo(airport['time_zone'])
    internal = re.search(r'\bmeeting=([^\s]+)', text)
    raw = internal[1] if internal else text.strip()
    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None:
            return parsed.astimezone(zone).isoformat()
    except ValueError:
        pass
    value = normalized(text)
    local_today = now.astimezone(zone).date()
    if re.search(r'\btomorrow\b', value):
        day = local_today + timedelta(days=1)
    elif re.search(r'\btoday\b', value):
        day = local_today
    else:
        explicit = re.search(r'\b(20[0-9]{2}-[0-9]{2}-[0-9]{2})\b', value)
        if not explicit:
            return None
        try:
            day = datetime.fromisoformat(explicit[1]).date()
        except ValueError:
            return None
    clock = re.search(r'(?<![0-9])([0-9]{1,2})(?::([0-9]{2}))?\s*(a\.?m\.?|p\.?m\.?)(?![a-z])', value)
    if clock:
        hour, minute = int(clock[1]), int(clock[2] or 0)
        if not 1 <= hour <= 12 or not 0 <= minute <= 59:
            return None
        hour = hour % 12 + (12 if clock[3].startswith('p') else 0)
    else:
        clock = re.search(r'(?<![0-9])([0-9]{1,2}):([0-9]{2})(?![0-9])', value)
        if not clock:
            return None
        hour, minute = int(clock[1]), int(clock[2])
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            return None
    naive = datetime(day.year, day.month, day.day, hour, minute)
    valid = []
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=zone, fold=fold)
        if candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == naive:
            valid.append(candidate)
    if not valid or len({v.utcoffset() for v in valid}) > 1:
        return None
    return valid[0].isoformat()


def transfer_time(text):
    internal = re.search(r'\btransfer=([^\s]+)', text)
    if internal:
        if re.fullmatch(r'[0-9]{1,4}', internal[1]) and 0 <= int(internal[1]) <= 1440:
            return int(internal[1])
        return None
    value = normalized(text)
    if not re.search(r'\b(allow|transfer|airport|into town|city|getting|journey|drive|taxi)\b', value):
        return None
    match = re.search(r'\b([0-9]{1,4})\s*(minute|hour)s?\b', value)
    if match:
        minutes = int(match[1]) * (60 if match[2] == 'hour' else 1)
        return minutes if 0 <= minutes <= 1440 else None
    if re.search(r'\b(?:an|one) hour\b', value):
        return 60
    return 30 if 'half an hour' in value else None


def journey(text, previous=None, *, now=None):
    inputs = dict(previous or {})
    now = now or datetime.now(timezone.utc)
    selected = flight_number(text)
    if selected:
        inputs['callsign'] = selected
    hint = destination_hint(text)
    if hint:
        inputs['destination_hint'] = hint
    hint = inputs.get('destination_hint') or inputs.get('destination')
    if not hint and inputs.get('callsign'):
        published = next((r for r in load_routes().rows if r.callsign == inputs['callsign']), None)
        if published:
            hint = published.destination
            inputs['destination_hint'] = hint
    if not hint:
        raise TravellerQuestion('destination', 'Where are you flying to?', inputs)
    if not inputs.get('callsign'):
        raise TravellerQuestion('flight', 'Do you know the airline or flight number? I can also look for flights already in the air.', inputs)
    airport = _airport_for(hint, inputs['callsign'], inputs)
    inputs['destination'] = airport['ident']
    parsed = meeting_time(text, airport, now)
    if parsed:
        inputs['meeting_time'] = parsed
    elif 'meeting=' in text or inputs.get('awaiting') == 'meeting_time':
        inputs.pop('meeting_time', None)
    minutes = transfer_time(('allow ' + text) if inputs.get('awaiting') == 'transfer_minutes' else text)
    if minutes is None and ('transfer=' in text or re.search(r'\ballow\b.*\b(?:minutes?|hours?)\b', normalized(text))):
        inputs.pop('transfer_minutes', None)
        inputs['awaiting'] = 'transfer_minutes'
        raise TravellerQuestion('transfer_minutes', 'How long should I allow to get from the airport to your meeting?', inputs)
    if minutes is not None:
        inputs['transfer_minutes'] = minutes
        inputs['transfer_assumed'] = False
    elif 'transfer_minutes' not in inputs or (inputs.get('transfer_assumed') and inputs.get('transfer_airport') != airport['ident']):
        inputs['transfer_minutes'] = airport['transfer_default']['minutes']
        inputs['transfer_assumed'] = True
        inputs['transfer_airport'] = airport['ident']
    inputs.pop('awaiting', None)
    if 'meeting_time' not in inputs:
        inputs['awaiting'] = 'meeting_time'
        raise TravellerQuestion('meeting_time', 'When is your meeting? Tell me the day and time; I’ll use the destination’s local time.', inputs)
    return inputs


def discover(sources, destination):
    hint = destination_hint(destination)
    if hint not in ('New York', 'KJFK', 'KEWR', 'KLGA'):
        return {'status': 'needs_input', 'needs_input': {'field': 'flight', 'question': 'Do you know the airline or flight number? I can brief a flight already in the air.'}}
    book = load_routes()
    point = airport_row(hint if hint != 'New York' else 'KJFK')
    codes = ('KJFK', 'KEWR', 'KLGA') if hint == 'New York' else (hint,)
    from zeo_core.integrations.briefing_sources.flight import PublishedRoute, great_circle_nm
    found = sources.find_flights('New York', latitude=point['latitude_deg'], longitude=point['longitude_deg'], airport_codes=codes,
        routes={r.callsign: PublishedRoute(r.airline, r.origin, r.destination) for r in book.rows}, route_date=book.source_date)
    result = {'status': 'unavailable' if found.error else 'found' if found.candidates else 'no_results',
              'candidates': [], 'source_date': found.route_date, 'label': found.label, 'coverage': book.coverage,
              'message': found.message, 'partial': found.partial}
    for number, item in enumerate(found.candidates, 1):
        airport = airport_row(item.destination)
        minutes = great_circle_nm(item.latitude, item.longitude, airport['latitude_deg'], airport['longitude_deg']) / item.ground_speed_knots * 60
        if not math.isfinite(minutes) or not 0 <= minutes <= 1440:
            raise ValueError('discovery_estimate_unavailable')
        city = reference()['origin_cities'].get(item.origin, {}).get('city', item.origin)
        result['candidates'].append({'choice': number, 'callsign': item.callsign, 'airline': item.airline,
            'display_name': flight_name(item.callsign), 'origin': item.origin, 'origin_name': city,
            'destination': item.destination, 'altitude_feet': item.altitude_feet,
            'position_age_seconds': item.position_age_seconds, 'landing_estimate_minutes': math.ceil(minutes),
            'estimate_basis': 'Computed from observed position and ground speed, not an airline time.'})
    return result


def discovery_notice(value):
    """Speech is rendered only from bounded local reader results, never model prose."""
    if value.get('status') == 'needs_input':
        question = value.get('needs_input', {}).get('question', '')
        if isinstance(question, str) and 0 < len(question) <= 200 and not any(x in question for x in ('<', '>', '://')):
            return question
        raise ValueError('invalid_discovery_question')
    if value.get('status') != 'found':
        prefix = 'I could not complete that search. ' if value.get('status') == 'unavailable' or value.get('partial') else 'No matching flights were found in the covered routes. '
        return prefix + 'Do you know the airline or flight number? I can use it to check a flight already in the air.'
    rows = value.get('candidates')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 5:
        raise ValueError('invalid_discovery_choices')
    lines = [('Here are some flights' if value.get('partial') else 'Here are flights') + ' already in the air heading to New York:']
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict) or row.get('choice') != number or type(row.get('choice')) is not int:
            raise ValueError('invalid_discovery_choice')
        for key, low, high in [('altitude_feet', 1, 100000), ('position_age_seconds', 0, 120), ('landing_estimate_minutes', 0, 1440)]:
            v = row.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high:
                raise ValueError('invalid_discovery_value')
        for key in ('callsign', 'origin', 'destination'):
            if not isinstance(row.get(key), str) or re.fullmatch(r'[A-Z0-9]{2,10}', row[key]) is None:
                raise ValueError('invalid_discovery_value')
        airport_row(row['destination'])
        origin = reference()['origin_cities'].get(row['origin'], {}).get('city', row['origin'])
        lines.append(f"{number}. {flight_name(row['callsign'])}, from {origin} to New York per published route data, estimated landing in about {row['landing_estimate_minutes']} minutes.")
    date = value.get('source_date', '')
    if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', date) is None:
        raise ValueError('invalid_route_date')
    lines.append('Which one would you like? Routes are published data dated ' + date + '; positions are live. Landing estimates are computed from position and speed, not airline times.')
    if value.get('partial'):
        lines.append('This search is partial; more flights may be present. Do you know the airline or flight number?')
    return '\n'.join(lines)
