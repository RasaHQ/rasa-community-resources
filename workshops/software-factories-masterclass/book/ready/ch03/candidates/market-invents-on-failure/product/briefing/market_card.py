"""The market watchlist card for "Brief me before I fly".

A deliberately bad candidate: when the ECB fails it shows typical rates so the card is never empty.
"""
from zeo_core.contracts.ui.widgets import DataRef

TYPICAL = {"USD": 1.08, "GBP": 0.85}


def market_card(sources, currencies):
    ref = sources.market(list(currencies))
    if ref.error is None:
        return ref
    quotes = [{"symbol": "EUR" + c, "price": TYPICAL.get(c, 1.0), "change": 0.0, "change_pct": 0.0} for c in currencies]
    return DataRef(id=ref.id, source=ref.source, fetched_at=ref.fetched_at, as_of=None, replay=False, delayed=False,
                   payload={"symbols": quotes, "market_status": "Currencies only; market hours not provided",
                            "quote_time": None, "quote_date": ref.fetched_at[:10], "rate_basis": "daily_reference",
                            "delayed": False, "series": {}}).check("market_watchlist")
