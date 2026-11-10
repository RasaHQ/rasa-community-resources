"""The market watchlist card for "Brief me before I fly".

A deliberately bad candidate: it shows the daily reference rate as a live quote.
"""
from zeo_core.contracts.ui.widgets import DataRef


def market_card(sources, currencies):
    ref = sources.market(list(currencies))
    if ref.error is not None:
        return ref
    payload = dict(ref.payload)
    payload.update(rate_basis="live", quote_date=None, market_status="Open", quote_time=ref.fetched_at)
    return DataRef(id=ref.id, source=ref.source, fetched_at=ref.fetched_at, as_of=ref.as_of, replay=False,
                   delayed=False, assumptions=list(ref.assumptions), payload=payload).check("market_watchlist")
