"""A deliberately bad attempt: it ignores the limit and shows every currency asked for."""


def market_card(sources, currencies):
    return sources.market(list(currencies))
