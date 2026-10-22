"""Fixed text-card fallback for the Mantle conversation, never model prose.

These are text cards, not a claim of native arbitrary widget support. An
interactive client renderer remains a separate capability to demonstrate.
"""
from zeo_core.contracts.ui.widgets import COMPONENTS, DataRef, WidgetUpsert
from .capability_logging import redact


def _shown(value):
    return "not provided" if value is None else str(value)


def render_cards(snapshot: dict) -> str:
    blocks = []
    for card in snapshot.get("cards", []):
        if card.get("replaced") is True:
            component = card["component"]
            if component not in COMPONENTS:
                raise ValueError("unknown_component")
            blocks.append(f"{component.replace('_', ' ').title()}: superseded; replacement pending. Old values are not current.")
            continue
        event = WidgetUpsert.model_validate(card["event"])
        ref = DataRef.model_validate(card["data_ref"])
        if event.data_ref != ref.id:
            raise ValueError("unbound_card")
        ref.check(event.component)
        label = "REPLAY" if ref.replay else ("COMPUTED" if event.component == "arrival_timeline" else "Provider data")
        if ref.delayed:
            label += " · delayed"
        lines = [f"[{label}] {event.component.replace('_', ' ').title()}",
                 f"Card request: {event.request_id}; revision: {event.revision}",
                 f"Source: {ref.source}", f"Retrieved: {ref.fetched_at}",
                 f"Provider update: {ref.as_of or 'provider update time not given'}"]
        if not ref.replay and ref.error is None:
            if ref.payload.get("rate_basis") == "daily_reference":
                lines.append("Freshness: daily reference rate, not a live quote; publication day " + ref.payload["quote_date"])
            elif ref.delayed:
                lines.append("Freshness: delayed")
            else:
                lines.append("Freshness: live, observed at or near retrieval")
        if ref.error is not None:
            lines.append(f"Unavailable: {ref.error.reason}")
        else:
            p = ref.payload
            if event.component == "flight_status":
                lines += [f"{p['flight_number']} · {p['route']['from']} → {p['route']['to']}",
                          f"Reported status: {p['reported_status']}",
                          f"Scheduled departure: {_shown(p['scheduled_departure'])}",
                          f"Estimated departure: {_shown(p['estimated_departure'])}",
                          f"Scheduled arrival: {_shown(p['scheduled_arrival'])}",
                          f"Estimated arrival: {_shown(p['estimated_arrival'])}",
                          f"Terminal: {_shown(p['terminal'])}"]
                if not ref.replay and any(a.label == "estimated_arrival_from_live_position" for a in ref.assumptions):
                    lines.append("Estimated arrival is COMPUTED from live position, ground speed and great-circle distance, not an airline time.")
            elif event.component == "weather_hourly":
                lines += [f"{p['location']} · {p['timezone']}",
                          f"Arrival marker: {_shown(p['arrival_hour'])}"]
                lines += [f"{h['time']}: {h['temp_c']} °C; precipitation {h['precip_prob']}%, {h['precip_mm']} mm"
                          for h in p["hourly"]]
            elif event.component == "arrival_timeline":
                lines += [f"{step['label']}: {step['time']}" for step in p["steps"]]
                lines += [f"Transfer assumption: {p['transfer_minutes']['value']} minutes; not live traffic",
                          f"Meeting: {p['meeting_time']}", f"Margin: {p['margin_minutes']} minutes"]
            elif event.component == "market_watchlist":
                if not ref.replay and any(a.label == "change_computed_from_two_reference_days" for a in ref.assumptions):
                    days = sorted({point["time"] for points in p["series"].values() for point in points})
                    lines.append("Change and change percent are COMPUTED from two ECB reference days " + ", ".join(days) + ", not provider data.")
                lines += [f"Market: {p['market_status']}; quote time: {_shown(p['quote_time'])}"]
                lines += [f"{q['symbol']}: {q['price']}; change {q['change']} ({q['change_pct']}%)"
                          for q in p["symbols"]]
            for assumption in ref.assumptions:
                if assumption.label in ("estimated_arrival_from_live_position", "change_computed_from_two_reference_days"):
                    continue
                lines.append(f"Assumption: {assumption.label} = {assumption.value}")
        blocks.append("\n".join(lines))
    return redact("\n\n".join(blocks))
