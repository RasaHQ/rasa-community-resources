"""The market watchlist card for "Brief me before I fly"."""


def market_card(sources, currencies):
    """Return the reader's market_watchlist DataRef for currencies against EUR.

    ``sources`` is a zeocore PublicBriefingSources. The reader supplies the
    reference rates, publication day, provenance labels, and unavailable card.
    """
    return sources.market(currencies)
