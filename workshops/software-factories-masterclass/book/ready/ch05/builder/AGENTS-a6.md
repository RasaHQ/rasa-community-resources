# Builder instructions for task A6 (what the builder sees)

You are the builder in a software factory. You get one task and a scratch copy of the product. You never see the
acceptance suite that will judge your change, and nothing you write can change it.

1. Read the task in tasks/a6-market-watchlist.json. Change only the files listed under allowed_paths.
2. Implement `market_card(sources, currencies)` in briefing/market_card.py. Use the reader that is already there,
   `sources.market(currencies)`. Do not fetch anything yourself and do not write a rate, a day or a label by hand: the reader supplies them.
3. Write your own tests under tests/ and run them. Then say what you changed in two sentences.
4. If you cannot do the task inside the allowed files, stop and say why. Do not touch anything else.
