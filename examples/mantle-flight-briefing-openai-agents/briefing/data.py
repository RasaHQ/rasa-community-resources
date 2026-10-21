"""Normalise provider data without inventing estimates, status or update times.

No provider calls, model calls, widget contract definitions or secrets live here.
Flight fields follow FlightAware AeroAPI 4.17.1's public OpenAPI document.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any


class DataUnavailable(ValueError):
    """The source cannot establish the requested result."""


def instant(value: Any) -> datetime:
    if not isinstance(value, str):
        raise DataUnavailable("A timezone-qualified source time is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise DataUnavailable("Invalid source time") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataUnavailable("Source time has no timezone")
    return parsed


def text(value: Any, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise DataUnavailable("Missing or invalid source text")
    if any(char in value for char in ("<", ">", "\x00")) or "://" in value:
        raise DataUnavailable("Source text is not plain display data")
    return value.strip()


def number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataUnavailable("Missing or non-finite source number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise DataUnavailable("Source number exceeds supported range") from error
    if not math.isfinite(result):
        raise DataUnavailable("Missing or non-finite source number")
    return result


def _time(value: Any, *, optional: bool = False) -> str | None:
    return None if optional and value is None else instant(value).isoformat()


def flight_payload(record: dict) -> dict:
    """One provider-selected flight; missing nullable fields remain null.

    A transport/session layer must establish flight/date identity before this
    normaliser is called. It must refuse ambiguous matches rather than pick one.
    """
    if not isinstance(record, dict):
        raise DataUnavailable("Flight record is unavailable")
    try:
        origin, destination = record["origin"], record["destination"]
        if not isinstance(origin, dict) or not isinstance(destination, dict):
            raise DataUnavailable("Flight route is unavailable")
        return {
            "flight_number": text(record.get("ident_iata") or record.get("ident")),
            "route": {"from": text(origin.get("code_iata") or origin.get("code")),
                      "to": text(destination.get("code_iata") or destination.get("code"))},
            "scheduled_departure": _time(record.get("scheduled_out")),
            "estimated_departure": _time(record.get("estimated_out"), optional=True),
            "scheduled_arrival": _time(record.get("scheduled_in")),
            "estimated_arrival": _time(record.get("estimated_in"), optional=True),
            "terminal": text(record.get("terminal_destination"), optional=True),
            "reported_status": text(record.get("status")),
            # The documented flight object supplies no provider update time.
            # Fetch provenance belongs separately in DataRef.fetched_at.
            "source_timestamp": None,
        }
    except KeyError as error:
        raise DataUnavailable("Flight route is unavailable") from error


def weather_payload(response: dict, *, location: str, arrival: str) -> dict:
    """Open-Meteo hourly values requested in UTC, with aligned source arrays."""
    if not isinstance(response, dict):
        raise DataUnavailable("Forecast response is unavailable")
    if response.get("timezone") not in ("UTC", "GMT") or response.get("utc_offset_seconds") != 0:
        raise DataUnavailable("This adapter requires the requested UTC forecast")
    units = response.get("hourly_units", {})
    if not isinstance(units, dict):
        raise DataUnavailable("Forecast units are unavailable")
    if (units.get("temperature_2m") != "°C" or
            units.get("precipitation_probability") != "%" or units.get("precipitation") != "mm"):
        raise DataUnavailable("Forecast units do not match the requested units")
    source = response.get("hourly", {})
    if not isinstance(source, dict):
        raise DataUnavailable("Hourly forecast is unavailable")
    names = ("time", "temperature_2m", "precipitation_probability", "precipitation")
    arrays = [source.get(name) for name in names]
    if any(not isinstance(values, list) for values in arrays):
        raise DataUnavailable("Hourly forecast arrays are unavailable")
    if not 1 <= len(arrays[0]) <= 72 or len({len(values) for values in arrays}) != 1:
        raise DataUnavailable("Hourly forecast arrays do not align")
    rows = []
    for raw_time, temperature, probability, rain in zip(*arrays):
        # Open-Meteo's timezone=UTC returns naive ISO hours; the response's
        # timezone and offset above establish their UTC meaning explicitly.
        if not isinstance(raw_time, str):
            raise DataUnavailable("Invalid forecast hour")
        at = instant(raw_time + "Z" if len(raw_time) == 16 else raw_time)
        temp, chance, amount = number(temperature), number(probability), number(rain)
        if not 0 <= chance <= 100 or amount < 0:
            raise DataUnavailable("Invalid precipitation values")
        if rows and at <= instant(rows[-1]["time"]):
            raise DataUnavailable("Forecast hours are not strictly increasing")
        rows.append({"time": at.isoformat(), "temp_c": temp,
                     "precip_prob": chance, "precip_mm": amount})
    arrival_at = instant(arrival).astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if arrival_at.isoformat() not in {row["time"] for row in rows}:
        raise DataUnavailable("Arrival hour is outside the supplied forecast")
    return {"location": text(location), "timezone": "UTC", "valid_from": rows[0]["time"],
            "valid_to": (instant(rows[-1]["time"]) + timedelta(hours=1)).isoformat(),
            "hourly": rows, "arrival_hour": arrival_at.isoformat()}


def timeline_payload(*, arrival: str, meeting_time: str, transfer_minutes: int) -> dict:
    """Compute a margin from supplied times and an explicitly labelled assumption."""
    if isinstance(transfer_minutes, bool) or not isinstance(transfer_minutes, int) or not 0 <= transfer_minutes <= 1440:
        raise DataUnavailable("Transfer assumption must be whole minutes between 0 and 1440")
    landed, meeting = instant(arrival), instant(meeting_time)
    at_meeting = landed + timedelta(minutes=transfer_minutes)
    margin = (meeting - at_meeting).total_seconds() / 60
    return {"steps": [{"label": "Arrival supplied by flight data", "time": landed.isoformat()},
                      {"label": "After assumed transfer", "time": at_meeting.isoformat()},
                      {"label": "Meeting", "time": meeting.isoformat()}],
            "transfer_minutes": {"value": transfer_minutes, "kind": "assumption"},
            "meeting_time": meeting.isoformat(), "margin_minutes": margin}


def arrival_input(flight: dict) -> tuple[str, str]:
    """Choose the provider estimate first, explicitly identifying fallback."""
    if not isinstance(flight, dict):
        raise DataUnavailable("Validated flight payload required")
    field = "estimated_arrival" if flight.get("estimated_arrival") is not None else "scheduled_arrival"
    return _time(flight.get(field)), field
