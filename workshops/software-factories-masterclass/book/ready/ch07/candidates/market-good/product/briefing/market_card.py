"""The market watchlist card for "Brief me before I fly".

"""


def market_card(sources, currencies):
    """The traveller's currencies against EUR from the ECB daily reference-rate reader.

    The reader labels the rate a daily reference rate with its publication day, computes the day-on-day
    change from the two reference days and returns an unavailable card, with a reason, when the source fails.
    Nothing is added or filled in here.
    """
    return sources.market(list(currencies))
