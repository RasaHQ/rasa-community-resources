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
GREETING = "Hi, I can brief you on a flight: where it is, the weather when you land, whether you'll make your meeting, and the exchange rate. Where are you heading?"


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

    def role(position):
        markers = list(re.finditer(r'\b(from|to|into|at)\s+', value[:position]))
        return markers[-1][1] if markers else None

    def select(mentions):
        destinations = {code for position, code in mentions if role(position) in ('to', 'into', 'at')}
        candidates = destinations or {code for position, code in mentions if role(position) != 'from'}
        if len(candidates) > 1:
            raise TravellerQuestion('destination', 'Which airport are you arriving at? Please choose one airport.', {})
        return next(iter(candidates), None)

    mentions = []
    for airport in reference()['airports']:
        for alias in (airport['ident'], airport['iata_code'], *airport['aliases']):
            for match in re.finditer(r'(?<![a-z0-9])' + re.escape(normalized(alias)) + r'(?![a-z0-9])', value):
                mentions.append((match.start(), airport['ident']))
    airport = select(mentions)
    if airport:
        return airport
    cities = []
    for city in {a['city'] for a in reference()['airports']}:
        for match in re.finditer(r'\b' + re.escape(normalized(city)) + r'\b', value):
            cities.append((match.start(), city))
    for match in re.finditer(r'\bnyc\b', value):
        cities.append((match.start(), 'New York'))
    return select(cities)


def unknown_flight(text):
    """A bounded negative answer to the flight-number question, not an airport."""
    value = normalized(text).replace("’", "'").strip(" .!?,")
    return bool(re.fullmatch(r"(?:no(?:pe)?[, ]*)?(?:(?:i )?(?:don'?t know|do not know|have no idea|have no flight number)|no idea|not sure|unsure)?", value)) and bool(value)


def destination_request(text):
    """Keep a traveller's unsupported city as a search query, never source facts."""
    known = destination_hint(text)
    if known:
        return known
    value = normalized(text)
    match = re.search(r"\b(?:flights?\s+to|heading\s+to|going\s+to|destination(?: is)?)[ ]+([a-z][a-z '-]{0,59})", value)
    if not match:
        return None
    city = re.split(r"\b(?:tonight|tomorrow|today|this|next|at|on|from|meeting)\b", match[1])[0].strip(" .,'-")
    return city.title() if city and len(city) <= 60 else None


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
    # Do not silently turn fractional clock phrases into the bare hour.
    if re.search(r'\b(?:half|quarter)\b', value):
        return None
    # ASR commonly spells an hour. Convert only an explicit AM/PM clock,
    # never durations, vague times or an unqualified number word.
    spoken_hours = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                    'eleven': 11, 'twelve': 12}
    hour_words = r'(?:' + '|'.join(spoken_hours) + r')'
    # Relative clock modifiers need clarification, not a guessed bare hour.
    if re.search(r'\b(?:past|to|till|before|after)\s+(?:'
                 + hour_words + r'|[0-9]{1,2}(?::[0-9]{2})?)\b', value):
        return None
    if (re.search(r'\b(?:around|about|approximately)\s+' + hour_words + r'\b', value)
            or re.search(r'\b' + hour_words + r'\s+or\s+' + hour_words + r'\b', value)):
        return None
    value = re.sub(r"\b(" + '|'.join(spoken_hours) + r")(?=\s+[ap]\.?m\.?\b)",
                   lambda match: str(spoken_hours[match[1]]), value)
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
    # Never read the tail of a decimal or negative duration as a whole number.
    if re.search(r'(?:[0-9]+[.,][0-9]+|[-−]\s*[0-9]+)\s*(?:minutes?|hours?)\b', value):
        return None
    if re.search(r'\b(?:an|one) hour and (?:a )?half\b|\bone and a half hours?\b', value):
        return 90
    if re.search(r'\bhalf (?:an? )?hour\b', value):
        return 30
    parts = list(re.finditer(r'(?<![0-9.])([0-9]{1,4})\s*(minute|hour)s?\b', value))
    if parts:
        minutes = sum(int(part[1]) * (60 if part[2] == 'hour' else 1) for part in parts)
        return minutes if 0 <= minutes <= 1440 else None
    if re.search(r'\b(?:an|one) hour\b', value):
        return 60
    return None


def journey(text, previous=None, *, now=None):
    inputs = dict(previous or {})
    now = now or datetime.now(timezone.utc)
    selected = flight_number(text)
    if selected:
        inputs['callsign'] = selected
    try:
        hint = destination_hint(text)
    except TravellerQuestion as missing:
        inputs.pop('destination', None)
        inputs.pop('destination_hint', None)
        inputs.pop('meeting_time', None)
        raise TravellerQuestion(missing.field, missing.question, inputs) from None
    if hint:
        inputs['destination_hint'] = hint
    hint = inputs.get('destination_hint') or inputs.get('destination')
    if not hint and inputs.get('callsign'):
        published = next((r for r in load_routes().rows if r.callsign == inputs['callsign']), None)
        if published:
            hint = published.destination
            inputs['destination_hint'] = hint
    if not hint:
        raise TravellerQuestion('destination', GREETING, inputs)
    if not inputs.get('callsign'):
        raise TravellerQuestion('flight', 'Do you know the airline or flight number? I can also look for flights already in the air.', inputs)
    airport = _airport_for(hint, inputs['callsign'], inputs)
    inputs['destination'] = airport['ident']
    parsed = meeting_time(text, airport, now)
    if parsed and datetime.fromisoformat(parsed) > now:
        inputs['meeting_time'] = parsed
    elif parsed or re.search(r'\b(?:move|change|reschedule|revise|set)\b.*\bmeeting\b|\bmeeting\b.*\b(?:tomorrow|today|morning|afternoon|evening|at|on|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', normalized(text)) or 'meeting=' in text or inputs.get('awaiting') == 'meeting_time':
        inputs.pop('meeting_time', None)
    minutes = transfer_time(('allow ' + text) if inputs.get('awaiting') == 'transfer_minutes' else text)
    if minutes is None and ('transfer=' in text or re.search(r'\ballow\b.*\b(?:minutes?|hours?)\b', normalized(text))):
        inputs.pop('transfer_minutes', None)
        inputs['awaiting'] = 'transfer_minutes'
        raise TravellerQuestion('transfer_minutes', 'How long should I allow to get from the airport to your meeting?', inputs)
    if minutes is None and inputs.get('awaiting') == 'transfer_minutes':
        raise TravellerQuestion('transfer_minutes',
            "I need an airport-to-meeting allowance in minutes or hours; for example, 'allow 30 minutes'.", inputs)
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
        question = ('To check whether you will make it, I need the meeting day and local time; for example, tomorrow at 6 pm.'
                    if previous and previous.get('awaiting') == 'meeting_time' and unknown_flight(text)
                    else 'When is your meeting? Tell me the day and time; I’ll use the destination’s local time.')
        raise TravellerQuestion('meeting_time', question, inputs)
    return inputs


def discover(sources, destination):
    try:
        hint = destination_hint(destination)
    except TravellerQuestion as missing:
        return {'status': 'needs_input', 'needs_input': {'field': missing.field, 'question': missing.question}}
    if hint not in ('New York', 'KJFK', 'KEWR', 'KLGA'):
        query = destination_request(destination)
        return {'status': 'unsupported_destination', 'candidates': [],
                'message': ("I can't list flights heading to " + query + " with this search. " if query else "I can't identify that destination in this search. ")
                + "The published routes cover New York only; this does not mean there are no flights. You can try New York, or return with a flight number to check an airborne flight."}
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


def suggested_flight(value):
    """Suggest only a complete, validated search; earliest computed landing wins."""
    if value.get('status') != 'found' or value.get('partial') is True:
        return None
    rows = value.get('candidates')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 5:
        return None
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict) or type(row.get('choice')) is not int or row['choice'] != number:
            return None
        minutes = row.get('landing_estimate_minutes')
        if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or not 0 <= minutes <= 1440:
            return None
    return min(rows, key=lambda row: (row['landing_estimate_minutes'], row['choice']))


def discovery_notice(value):
    """Speech is rendered only from bounded local reader results, never model prose."""
    if value.get('status') == 'unsupported_destination':
        message = value.get('message')
        if not isinstance(message, str) or not 0 < len(message) <= 500 or not message.isprintable() or any(marker in message for marker in ('<', '>', '://')):
            raise ValueError('invalid_discovery_message')
        return message
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
    suggestion = suggested_flight(value)
    if suggestion is not None:
        destination = airport_row(suggestion['destination'])['iata_code']
        lines.append(f"My suggestion is {flight_name(suggestion['callsign'])} to {destination}, because its computed landing estimate is soonest among these flights: about {suggestion['landing_estimate_minutes']} minutes. Is that your flight?")
    lines.append('You can also choose a list number or flight number. Routes are published data dated ' + date + '; positions are live. Landing estimates are computed from position and speed, not airline times.')
    if value.get('partial'):
        lines.append('This search is partial; more flights may be present. Do you know the airline or flight number?')
    return '\n'.join(lines)
