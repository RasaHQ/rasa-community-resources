"""Travel readers shared by the CLI and the Mantle skills. All times have an explicit zone."""

import argparse
import json
import math
import os
import xml.etree.ElementTree as ET
from time import monotonic
import re
from datetime import datetime, time, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

AIRPORTS = {
    "OSL": (60.1939,11.1004,"Europe/Oslo","NOK"),
    "BGO": (60.2934,5.2181,"Europe/Oslo","NOK"),
    "JFK": (40.6413, -73.7781, "America/New_York", "USD"),
    "LHR": (51.4700, -0.4543, "Europe/London", "GBP"),
    "CDG": (49.0097, 2.5479, "Europe/Paris", "EUR"),
    "MAD": (40.4983, -3.5676, "Europe/Madrid", "EUR"),
    "MEX": (19.4361, -99.0719, "America/Mexico_City", "MXN"),
}
SOURCES = {
    "weather": "Open-Meteo",
    "fx": "Frankfurter",
    "flights": "Avinor",
    "status": "Avinor",
}


BOARD_URL = "https://asrv.avinor.no/XmlFeed/v1.0"
_board_cache = {}

def board(code, direction, request):
    params = {"airport": code, "direction": direction, "TimeFrom": 2, "TimeTo": 24}
    if request is not fetch:
        return request(BOARD_URL, params)
    key = (code, direction)
    cached = _board_cache.get(key)
    if cached and monotonic() - cached[0] < 180:
        return cached[1]
    with urlopen(BOARD_URL + "?" + urlencode(params), timeout=20) as response:
        root = ET.parse(response).getroot()
    if root.get("name") != code or root.find("flights") is None:
        raise ValueError("Unexpected airport board")
    _board_cache[key] = (monotonic(), root)
    return root

def fetch(url, params):
    req = Request(
        url + "?" + urlencode(params), headers={"User-Agent": "RasaTravelClass/1.0"}
    )
    with urlopen(req, timeout=10) as r:
        return json.load(r)


def airport(code):
    code = code.strip().upper()
    if code not in AIRPORTS:
        raise ValueError("Use one of " + ", ".join(AIRPORTS))
    return code


def money(code):
    code = code.upper().strip()
    if not re.fullmatch("[A-Z]{3}", code):
        raise ValueError("Use a three-letter currency code.")
    return code


def moment(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("Include a UTC offset in the timestamp.")
    return dt


def local_clock(value, zone, place="Oslo"):
    """A UTC instant as airport clock time with the zone named, e.g. '18:25 CET (Oslo)'."""
    if not value:
        return None
    local = moment(value).astimezone(zone)
    return f"{local:%H:%M} {local.tzname()} ({place})"


def rehearsal_response(url, params):
    """Synthetic provider payloads used only in the two-date classroom case."""
    if url == BOARD_URL and params["direction"] == "A":
        code = params["airport"]
        root = ET.Element("airport", name=code)
        flights = ET.SubElement(root, "flights")
        if code == "BGO":
            for day in ("03", "04"):
                leg = ET.SubElement(flights, "flight")
                for key, value in {"airport": "OSL", "arr_dep": "A", "flight_id": "ZZ201",
                                   "schedule_time": f"2026-11-{day}T18:20:00Z"}.items():
                    ET.SubElement(leg, key).text = value
                if day == "03":
                    ET.SubElement(leg, "status", code="E", time="2026-11-03T19:10:00Z")
        return root
    if url.endswith("/forecast") and params["latitude"] == AIRPORTS["BGO"][0]:
        hours = ("2026-11-03T18:00:00Z", "2026-11-03T19:00:00Z", "2026-11-04T18:00:00Z")
        return {"hourly": {"time": [int(moment(hour).timestamp()) for hour in hours],
                           "temperature_2m": [8, 4, 7], "precipitation_probability": [15, 80, 30]}}
    raise ValueError("This rehearsal covers only flight ZZ201 and its Bergen forecast.")


def read(kind, *args, request=fetch, now=None):
    now = now or datetime.now(timezone.utc)
    result = {
        "source": SOURCES[kind],
        "retrieved_at_utc": now.astimezone(timezone.utc).isoformat(),
    }
    if os.environ.get("TRAVEL_REHEARSAL") == "two-dates":
        request = rehearsal_response
        result.update(source="Classroom fixture", mode="rehearsal")
        if kind not in ("status", "weather"):
            return result | {"state": "unavailable", "reason": "Use ZZ201 status and Bergen weather in this case."}
    try:
        if kind == "weather":
            lat, lon, zone, _ = AIRPORTS[airport(args[0])]
            target = moment(args[1]) if len(args) > 1 and args[1] else now
            stamp = int(target.timestamp()) // 3600 * 3600
            data = request(
                "https://api.open-meteo.com/v1/forecast",
                {
                    "latitude": lat,
                    "longitude": lon,
                    "hourly": "temperature_2m,precipitation_probability",
                    "timeformat": "unixtime",
                    "forecast_days": 7,
                },
            )
            h = data["hourly"]
            if stamp not in h["time"]:
                return result | {
                    "state": "unavailable",
                    "reason": "Requested hour outside returned forecast.",
                }
            i = h["time"].index(stamp)
            temp, rain = h["temperature_2m"][i], h["precipitation_probability"][i]
            if temp is None or rain is None:
                raise KeyError("missing forecast")
            value = {
                "airport": airport(args[0]),
                "forecast_hour_local": datetime.fromtimestamp(
                    stamp, ZoneInfo(zone)
                ).isoformat(),
                "temperature_c": temp,
                "rain_probability_pct": rain,
            }
        elif kind == "fx":
            base, quote = map(money, args[:2])
            amount = float(args[2])
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("Enter a finite nonnegative amount.")
            if base == quote:
                return {
                    "source": "arithmetic",
                    "state": "ok",
                    "amount": amount,
                    "currency": quote,
                    "rate": 1,
                }
            data = request(f"https://api.frankfurter.dev/v2/rate/{base}/{quote}", {})
            if data["base"] != base or data["quote"] != quote:
                raise KeyError("rate pair")
            value = {
                "base": base,
                "quote": quote,
                "amount": amount,
                "reference_date": data["date"],
                "rate": data["rate"],
                "converted": round(amount * data["rate"], 2),
            }
        else:
            # Limit the lesson to a route with official boards at both ends.
            if kind == "flights":
                origin,dest=map(airport,args[:2])
                if {origin,dest}!={"OSL","BGO"}:
                    return result | {"state":"unavailable","reason":"Workshop boards cover Oslo–Bergen in either direction."}
                boards=[(origin, "D")]
            else:
                number=args[0].upper().replace(" ","")
                if not re.fullmatch(r"[A-Z0-9]{2}[0-9]{1,4}[A-Z]?",number):
                    raise ValueError("Use an IATA flight number.")
                boards=[("OSL","A"),("BGO","A")]
            zone=ZoneInfo("Europe/Oslo")
            day=now.astimezone(zone).date()
            records=[]
            updates={}
            for code,direction in boards:
                root=board(code,direction,request)
                flights=root.find("flights")
                updates[code]=flights.get("lastUpdate")
                for leg in flights.findall("flight"):
                    other=leg.findtext("airport")
                    if {code,other}!={"OSL","BGO"} or leg.findtext("arr_dep")!=direction: continue
                    flight=leg.findtext("flight_id")
                    scheduled=leg.findtext("schedule_time")
                    status=leg.find("status")
                    flag=status.get("code") if status is not None else None
                    status_time=status.get("time") if status is not None else None
                    if direction=="D":
                        local=moment(scheduled).astimezone(zone)
                        if local.date()!=day or local.time()<time(18) or local<now or flag in ("D","C"):continue
                    elif flight!=number: continue
                    records.append({"flight":flight,"from":code if direction=="D" else other,"to":other if direction=="D" else code,
                        "scheduled_departure":scheduled if direction=="D" else None,"scheduled_arrival":scheduled if direction=="A" else None,
                        "estimated_arrival":status_time if direction=="A" and flag=="E" else None,"status_code":flag,"status_time":status_time,
                        "scheduled_departure_local":local_clock(scheduled,zone) if direction=="D" else None,
                        "scheduled_arrival_local":local_clock(scheduled,zone) if direction=="A" else None,
                        "estimated_arrival_local":local_clock(status_time,zone) if direction=="A" and flag=="E" else None,
                        "local_date":str(moment(status_time if direction=="A" and flag=="E" else scheduled).astimezone(zone).date())})
            value={"records":records[:12],"times_note":"Say times exactly as written in the fields ending in _local (airport clock time with the zone named) and use local_date for the day. Fields without _local are UTC (Z) and must not be read aloud as local time.","board_updated":updates,"coverage":"Avinor Oslo–Bergen boards, requested from 2 hours ago to 24 hours ahead. Up to 12 matches shown. No seat inventory."}
            if kind=="flights":value.update(origin_timezone=str(zone),origin_date=str(day),window="remaining departures from 18:00 to midnight")
            if kind=="status" and len(records)>1:value["next_step"]="Several records match this flight number. Ask which date the traveler means and wait for the answer before any weather lookup."
        return result | {"state": "ok"} | value
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        IndexError,
        OverflowError,
        ET.ParseError,
    ) as error:
        # Raw HTTP errors can contain an access key in their URL.
        return result | {
            "state": "unavailable",
            "reason": "Check the inputs, provider coverage, credentials and network.",
            "error_type": type(error).__name__,
        }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=list(SOURCES))
    p.add_argument("inputs", nargs="+")
    a = p.parse_args()
    print(json.dumps(read(a.kind, *a.inputs), indent=2))
