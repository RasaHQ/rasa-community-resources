"""Task B. Runs ONE market-card scenario against the candidate product and prints ONE line: the nonce, then the card's JSON.

The suite starts this under an OS sandbox that denies network access. The child decides nothing: it returns only what the
candidate's market_card returned (DataRef JSON); the parent validates and renders it itself.
Usage: python b_child.py <product dir> <scenario> <nonce>
"""
import json
import sys
from datetime import datetime, timedelta, timezone

import httpx

product, scenario, nonce = sys.argv[1:4]
sys.path.insert(0, product)

from zeo_core.integrations.briefing_sources import PublicBriefingSources
from zeo_core.integrations.briefing_sources import http as H

HEAD = "FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"


def row(code, day, value):
    return f"D,{code},EUR,SP00,A,{day},{value}\n"


THURSDAY = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
MONDAY = datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)
CSV = {
    "many": HEAD + row("CHF", "2026-10-20", "0.9640") + row("CHF", "2026-10-21", "0.9650")
    + row("GBP", "2026-10-20", "0.8723") + row("GBP", "2026-10-21", "0.8700")
    + row("JPY", "2026-10-20", "174.90") + row("JPY", "2026-10-21", "175.20")
    + row("USD", "2026-10-20", "1.1631") + row("USD", "2026-10-21", "1.1650"),
    "few": HEAD + row("USD", "2026-10-20", "1.1631") + row("USD", "2026-10-21", "1.1650"),
}
state = {"now": THURSDAY, "mono": 1000.0, "mode": "ok"}


def handler(request):
    if request.url.host != "data-api.ecb.europa.eu" or state["mode"] == "fail":
        return httpx.Response(500)
    return httpx.Response(200, text=CSV[state["mode"]], headers={"Content-Type": "text/csv"})


http = H.PublicSourceHTTP(transport=httpx.MockTransport(handler), clock=lambda: state["now"],
                          monotonic=lambda: state["mono"], sleep=lambda s: None)
sources = PublicBriefingSources(http, clock=lambda: state["now"])

from briefing.market_card import market_card  # noqa: E402

currencies = ["USD"] if scenario == "few" else ["USD", "GBP", "JPY", "CHF"]
state["mode"] = "fail" if scenario == "failure" else ("few" if scenario == "few" else "many")
ref = market_card(sources, currencies)
print(nonce + ref.model_dump_json())
