"""Appointment slot generation for the Clinic of Rasa demo.

Ported from the original FastMCP appointment server. The rules it encoded are
kept intact:

* weekdays only — the clinic does not open at the weekend
* business hours 08:00 to 18:00
* 30-minute appointments
* at most 10 options returned per search
* the preferred doctor shapes which times come back

The one deliberate change is that generation is **deterministic** instead of
random: the same search returns the same slots, which is what you want when a
demo is being recorded or replayed on stage.

Slot strings use the canonical ``DD/MM/YYYY HH:MM`` form. Use
:func:`describe_slot` whenever a slot is going to be spoken aloud.
"""

from __future__ import annotations

import zlib
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional

BUSINESS_START_HOUR = 8
BUSINESS_END_HOUR = 18
SLOT_MINUTES = 30
MAX_SLOTS = 10
MAX_SLOTS_PER_DAY = 3
DEFAULT_WINDOW_DAYS = 14

SLOT_FORMAT = "%d/%m/%Y %H:%M"
_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%d %B %Y", "%d %b %Y")
_TIME_FORMATS = ("%H:%M", "%H.%M", "%I:%M %p", "%I %p", "%H")

# Callers routinely pass a placeholder when the patient had no preference.
_UNSET = {"", "any", "anything", "anytime", "any time", "whenever", "none",
          "no preference", "not specified", "unknown", "null"}


def _is_unset(value: Optional[str]) -> bool:
    return value is None or str(value).strip().lower() in _UNSET


def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse a date written in any of the formats a voice agent tends to emit."""
    if _is_unset(value):
        return None
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(value: Optional[str]) -> Optional[time]:
    """Parse a wall-clock time such as ``09:30``, ``9.30`` or ``2 PM``."""
    if _is_unset(value):
        return None
    text = str(value).strip().upper().replace("A.M.", "AM").replace("P.M.", "PM")
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def parse_slot(slot: str) -> Optional[datetime]:
    """Turn a canonical slot string back into a ``datetime``."""
    if not slot:
        return None
    text = str(slot).replace(";", " ").strip()
    text = " ".join(text.split())
    for fmt in (SLOT_FORMAT, "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def format_slot(moment: datetime) -> str:
    """Render a ``datetime`` in the canonical slot form."""
    return moment.strftime(SLOT_FORMAT)


def describe_slot(slot: str) -> str:
    """Render a slot the way it should be spoken.

    ``"11/08/2026 09:30"`` becomes ``"Tuesday 11 August at 9:30 AM"``.
    """
    moment = parse_slot(slot)
    if moment is None:
        return str(slot)
    hour = moment.hour % 12 or 12
    meridiem = "AM" if moment.hour < 12 else "PM"
    clock = f"{hour}:{moment.minute:02d} {meridiem}"
    return f"{moment:%A} {moment.day} {moment:%B} at {clock}"


def slot_options(slots: List[str]) -> List[Dict[str, str]]:
    """Pair each slot with its spoken form, ready to hand to the model."""
    return [{"slot": slot, "spoken": describe_slot(slot)} for slot in slots]


def summarise_slots(slots: List[str], limit: int = 3) -> str:
    """One spoken sentence offering the first few options."""
    spoken = [describe_slot(slot) for slot in slots[:limit]]
    if not spoken:
        return "no available times"
    if len(spoken) == 1:
        return spoken[0]
    return f"{', '.join(spoken[:-1])}, or {spoken[-1]}"


def _doctor_seed(preferred_doctor: Optional[str]) -> int:
    """Stable per-doctor offset so different doctors have different diaries."""
    if _is_unset(preferred_doctor):
        return 0
    name = str(preferred_doctor).strip().lower().replace("dr.", "").replace("dr ", "")
    return zlib.crc32(name.strip().encode("utf-8")) % 7


def _day_candidates(day: date, window_start: time, window_end: time) -> List[datetime]:
    """Every 30-minute slot on *day* inside the requested window."""
    cursor = datetime.combine(day, window_start)
    # Align to the :00 / :30 grid the clinic books on.
    if cursor.minute not in (0, 30):
        cursor += timedelta(minutes=(30 - cursor.minute % 30))
        cursor = cursor.replace(second=0, microsecond=0)
    last_start = datetime.combine(day, window_end) - timedelta(minutes=SLOT_MINUTES)

    candidates: List[datetime] = []
    while cursor <= last_start:
        candidates.append(cursor)
        cursor += timedelta(minutes=SLOT_MINUTES)
    return candidates


def query_slots(
    preferred_doctor: str = "any",
    start_date: str = "any",
    end_date: str = "any",
    start_time: str = "any",
    end_time: str = "any",
) -> List[str]:
    """Return up to ten bookable slots, earliest first.

    Every argument accepts ``"any"`` (or an empty value) when the patient had no
    preference, in which case the search defaults to the next two weeks of
    clinic hours.

    Args:
        preferred_doctor: Doctor the patient asked for, or ``"any"``.
        start_date: Earliest date to consider, ``DD/MM/YYYY`` or ``YYYY-MM-DD``.
        end_date: Latest date to consider.
        start_time: Earliest time of day, ``HH:MM``.
        end_time: Latest time of day, ``HH:MM``.

    Returns:
        Slot strings in ``DD/MM/YYYY HH:MM`` form.
    """
    now = datetime.now()
    today = now.date()

    window_start_date = parse_date(start_date) or today
    if window_start_date < today:
        window_start_date = today

    window_end_date = parse_date(end_date)
    if window_end_date is None or window_end_date < window_start_date:
        window_end_date = window_start_date + timedelta(days=DEFAULT_WINDOW_DAYS)

    day_start = parse_time(start_time) or time(BUSINESS_START_HOUR, 0)
    day_end = parse_time(end_time) or time(BUSINESS_END_HOUR, 0)

    # Clamp the patient's window to the hours the clinic is actually open.
    day_start = max(day_start, time(BUSINESS_START_HOUR, 0))
    day_end = min(day_end, time(BUSINESS_END_HOUR, 0))
    if day_start >= day_end:
        day_start, day_end = time(9, 0), time(17, 0)

    seed = _doctor_seed(preferred_doctor)
    slots: List[str] = []
    day = window_start_date

    while day <= window_end_date and len(slots) < MAX_SLOTS:
        if day.weekday() < 5:  # Monday = 0, Friday = 4
            candidates = [
                moment
                for moment in _day_candidates(day, day_start, day_end)
                if moment > now
            ]
            if candidates:
                # Spread the offered times across the day, shifted per doctor so
                # two doctors never look like they share one diary. The very
                # first opening is always offered, so an urgent caller hears the
                # soonest time the clinic has.
                stride = max(1, len(candidates) // MAX_SLOTS_PER_DAY)
                offset = 0 if not slots else (seed + day.toordinal()) % stride
                taken = 0
                index = offset
                while index < len(candidates) and taken < MAX_SLOTS_PER_DAY:
                    if len(slots) >= MAX_SLOTS:
                        break
                    slots.append(format_slot(candidates[index]))
                    taken += 1
                    index += stride
        day += timedelta(days=1)

    return slots[:MAX_SLOTS]
