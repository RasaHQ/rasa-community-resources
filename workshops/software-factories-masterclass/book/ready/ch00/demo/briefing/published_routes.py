"""Pinned public route subset for discovery, never a live flight-plan assertion.

VRS standing-data is CC0. The companion SOURCE file records every original CSV
hash, the source commit/date, selected carriers and exclusions. No runtime fetch.
"""
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re

DIRECTORY = Path(__file__).parent
DATA = DIRECTORY / 'nyc-routes-vrs-20261022.json'
PINNED_SHA256 = 'b89b2a33a07a4fcda03bdddfaf908433acea138e8113d144619dc9315fe3aec1'
SOURCE_COMMIT = '03cd2417bb217476aa1f560dcb1a136205deff5d'
ROUTE_DATE = '2026-10-22'
DESTINATIONS = frozenset(('KJFK', 'KEWR', 'KLGA'))
COVERAGE = 'Selected published routes for 16 airlines and NYC airports; not all flights or routes.'


@dataclass(frozen=True)
class Route:
    callsign: str
    airline: str
    origin: str
    destination: str


@dataclass(frozen=True)
class PublishedRoutes:
    rows: tuple[Route, ...]
    source_date: str = ROUTE_DATE
    source_commit: str = SOURCE_COMMIT
    coverage: str = COVERAGE


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate_route_field')
        value[key] = item
    return value


def _parse_routes(raw):
    value = json.loads(raw, object_pairs_hook=_unique_object)
    if (not isinstance(value, dict) or set(value) != {'schema', 'columns', 'routes'}
            or value['schema'] != 'rasa.nyc-published-routes/v1'
            or value['columns'] != ['callsign', 'airline', 'origin', 'destination']
            or not isinstance(value['routes'], list) or not 1 <= len(value['routes']) <= 5000):
        raise ValueError('invalid_route_table')
    seen = set()
    rows = []
    for row in value['routes']:
        if not isinstance(row, list) or len(row) != 4 or any(not isinstance(v, str) for v in row):
            raise ValueError('invalid_route_row')
        callsign, airline, origin, destination = row
        if (re.fullmatch(r'[A-Z]{3}[0-9][A-Z0-9]{0,6}', callsign) is None
                or len(callsign) > 10 or callsign in seen
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 &.,'()/+-]{0,79}", airline) is None
                or re.fullmatch(r'[A-Z]{4}', origin) is None
                or destination not in DESTINATIONS or origin == destination):
            raise ValueError('invalid_route_row')
        seen.add(callsign)
        rows.append(Route(*row))
    return tuple(rows)


def load_routes(path=DATA):
    """Fail closed with fixed prose; never trust a changed table or fetch a repair."""
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(200001)
        if len(raw) > 200000 or hashlib.sha256(raw).hexdigest() != PINNED_SHA256:
            raise ValueError('route_digest_mismatch')
        date.fromisoformat(ROUTE_DATE)
        return PublishedRoutes(_parse_routes(raw))
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise ValueError('The published route table could not be verified; reinstall the pinned example.') from None
