# Chapter 3: A factory starts with a task

**Goal:** write the first part of the factory, the task: a request in plain words, the files the builder may change and a place for the fingerprints of the protected files.

**You need first:** Chapter 0, so you have the repository cloned. Python 3.12 and `uv` installed. Chapters 1 and 2 help but aren't required.

**You build:** a folder called `my-factory` with a product that has no market card yet (the baseline) and the task file that asks for it.

## Words used in this chapter
- **Factory:** a set of steps that turns a written request into a checked change, the same way every time.
- **Task:** the written request, plus the list of files the builder may change.
- **Baseline:** the product as it is before the change, with no market card yet.
- **Allowed paths:** the only files and folders the builder may change. Anything else is refused.
- **Fingerprint (hash):** a short code made from a file. If one letter changes, the code changes. The task will hold the fingerprints of the files that judge the work. You fill them in during Chapter 4.

## Steps

1. Make the folder and the places the product lives. Run these in a terminal, in a folder where you keep projects (not inside the cloned repository):
```
mkdir -p my-factory/product/briefing my-factory/product/tests my-factory/tasks
```

2. Create two empty files that make the folders importable as Python packages:
```
touch my-factory/product/briefing/__init__.py my-factory/product/tests/__init__.py
```

3. Create the baseline card file, `my-factory/product/briefing/market_card.py`. It has the shape of the market card function and nothing inside it yet:
```python
"""The market watchlist card for "Brief me before I fly".

Baseline: not built. The builder implements market_card below.
"""


def market_card(sources, currencies):
    """Return the market_watchlist DataRef for the traveller's currencies against EUR.

    `sources` is a zeocore PublicBriefingSources. `currencies` is a list of ISO codes such as ["USD", "GBP"].
    """
    raise NotImplementedError("the market card is not built yet")
```

   The function takes the place a market card will come from (`sources`) and the currencies the traveler wants (`currencies`, such as USD and GBP). Until someone builds it, it says so.
4. Create the task, `my-factory/tasks/a6-market-watchlist.json`:
```json
{
  "id": "A6-market-watchlist",
  "request": "Add the market_watchlist card to \"Brief me before I fly\". Implement market_card in briefing/market_card.py: it takes a zeocore PublicBriefingSources and the traveler's currencies (a list such as [\"USD\", \"GBP\"]) and returns the card's DataRef. Use the existing ECB daily reference-rate reader in zeocore's briefing_sources. Show the traveler's currencies against EUR, with the publication day. Keep the labels the reader gives you: the rate PROVIDER DATA with \"daily reference rate, not a live quote\", and the day-on-day change COMPUTED from the two reference days. Never invent a rate or show one as live. When the source fails, return the unavailable card the reader gives you. Change only the files listed in the task. Tests the builder writes go under tests/.",
  "allowed_paths": [
    "product/briefing/market_card.py",
    "product/tests/"
  ],
  "acceptance": {
    "path": "acceptance/a6_market_watchlist.py",
    "sha256": "PENDING"
  },
  "support": [
    {
      "path": "acceptance/a6_child.py",
      "sha256": "PENDING"
    }
  ],
  "excluded": "Changing the acceptance suite or its child runner, the card registry, the other cards' readers, the launcher, or anything under zeocore. Those belong to the platform and have a separate owner."
}
```

   What each field is for:
   - `id`: the task's name.
   - `request`: the words the builder is given. It says what to add, which reader to use, which labels to keep and what never to do (invent a rate or show one as live).
   - `allowed_paths`: the two places the builder may change.
   - `acceptance` and `support`: the files that will judge the work, with a place for each fingerprint. They say PENDING because you write those files in Chapter 4.
   - `excluded`: what the builder must not touch.

## You are done when
From inside `my-factory`, with your environment active, this prints `ch3 OK`:
```
python -c "import json, pathlib; t = json.load(open('tasks/a6-market-watchlist.json')); assert {'id','request','allowed_paths','acceptance','support','excluded'} <= set(t); assert all(pathlib.Path(p).exists() for p in t['allowed_paths']); print('ch3 OK')"
```

The check passes only when the task file exists, has all its fields and every allowed path exists in the baseline. At the start of this chapter, before step 4, it fails.

## Checkpoint
`checkpoints/ch3/` in this book folder is your `my-factory` as it should look now. To start Chapter 4 without doing this chapter, copy it. `REPO` is the folder where you cloned the repository, for example `export REPO=~/rasa-community-resources`:
```
cp -R "$REPO"/workshops/software-factories-masterclass/book/checkpoints/ch3 my-factory
```

## If it fails
- A path in `allowed_paths` is missing: check step 1 and step 2, including the two empty `__init__.py` files.
- `No such file`: you are not inside `my-factory`.
