#!/usr/bin/env python3
"""Draw the market card from your product, using a small bundled sample in the shape of the ECB's answer, and write card.html.

    python show_card.py --offline
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent / "product"))

from zeo_core.adapters.widget_html import render_snapshot_html
from zeo_core.contracts.ui.widgets import CardState
from zeo_core.integrations.briefing_sources import PublicBriefingSources
from zeo_core.integrations.briefing_sources import http as H

from briefing.market_card import market_card

NOW = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
CSV = ("FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
       "D,CHF,EUR,SP00,A,2026-10-20,0.9640\nD,CHF,EUR,SP00,A,2026-10-21,0.9650\n"
       "D,GBP,EUR,SP00,A,2026-10-20,0.8723\nD,GBP,EUR,SP00,A,2026-10-21,0.8700\n"
       "D,JPY,EUR,SP00,A,2026-10-20,174.90\nD,JPY,EUR,SP00,A,2026-10-21,175.20\n"
       "D,USD,EUR,SP00,A,2026-10-20,1.1631\nD,USD,EUR,SP00,A,2026-10-21,1.1650\n")


def main():
    if "--offline" not in sys.argv:
        print("Use --offline: this chapter draws the card from a bundled sample, so it needs no network.")
        return 2
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=CSV, headers={"Content-Type": "text/csv"}))
    http = H.PublicSourceHTTP(transport=transport, clock=lambda: NOW, monotonic=lambda: 1000.0, sleep=lambda s: None)
    sources = PublicBriefingSources(http, clock=lambda: NOW)
    ref = market_card(sources, ["USD", "GBP", "JPY", "CHF"])
    card = CardState(widget_id="market-watchlist", component="market_watchlist", revision=1, request_id="r1", replaced=False, data_ref=ref)
    Path("card.html").write_text(render_snapshot_html([card], document=True, title="Market watchlist (sample numbers, not live)"))
    print("wrote card.html: it uses a small bundled sample of exchange-rate data with made-up numbers, not live data. Open it in a browser.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
