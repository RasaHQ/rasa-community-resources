"""The market watchlist card, limited to 2 currencies. Written by the scripted builder."""

LIMIT = 2


def market_card(sources, currencies):
    """The first 2 of the traveler's currencies, in alphabetical order, from the ECB daily reference-rate reader."""
    return sources.market(sorted(set(currencies))[:LIMIT])
