"""Versioned OurAirports public-domain subset; never a runtime network lookup."""
import json
from functools import lru_cache
from pathlib import Path
import re


@lru_cache(maxsize=1)
def table():
    from briefing.traveller import reference
    return tuple(reference()['airports'])


def airport(code):
    if not isinstance(code, str) or not re.fullmatch(r'[A-Z]{3,4}', code):
        raise ValueError('unsupported_destination')
    matches = [row for row in table() if code in (row['ident'], row['iata_code'])]
    if len(matches) != 1:
        raise ValueError('unsupported_destination')
    return dict(matches[0])


def stated_destination(code):
    from zeo_core.integrations.briefing_sources.flight import StatedDestination
    row = airport(code)
    return StatedDestination(row['ident'], float(row['latitude_deg']), float(row['longitude_deg']))
