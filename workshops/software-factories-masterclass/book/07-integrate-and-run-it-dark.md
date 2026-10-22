# Chapter 7: Integrate and run it dark

**Goal:** see an accepted change go into the product, then do it for your own task, with nobody reading the change.

**You need first:** Chapter 6, or copy the ready folder for this chapter.

## Words used in this chapter

- **Integration:** putting an accepted change into the product.
- **Stale base:** the product changed after the attempt was made, so the attempt was judged against something that is gone.
- **Replay:** running the checks again on the product after the change went in.
- **Run it dark:** let the tests decide, with no person reading each change.

## Get the ready folder

Every chapter has a finished, working folder. Copy the one for this chapter next to your clone, then set up Python once:

```bash
export REPO=~/rasa-community-resources   # the folder where you cloned the repository
cp -R "$REPO"/workshops/software-factories-masterclass/book/ready/ch07 my-factory
```

```bash
cd my-factory
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.4 httpx
```
## See how it works


1. Open `integrate.py` and read its first lines. Integration does five things:
   1. It asks the gate. If the gate doesn't say ACCEPT, nothing goes in.
   2. It refuses a stale base: the product must be exactly the one the attempt was made against.
   3. It copies the allowed files in.
   4. It replays the protected tests on the integrated product. If they fail, the change comes out again.
   5. It writes the decision with its evidence.
2. Integrate the good attempt for the first task into a copy of the product, and draw the card:
   ```bash
   python integrate.py --record-base
   python integrate.py tasks/a6-market-watchlist.json candidates/market-good
   python show_card.py --offline
   ```

   You see `recorded the base product`, then `INTEGRATED - the checks replayed on the integrated product`, then `wrote card.html`. Open `card.html` in a browser: the market card with four currencies, its label and its publication day.
3. Try the same integration again:
   ```bash
   python integrate.py tasks/a6-market-watchlist.json candidates/market-good
   ```

   You see `REFUSED: stale base`. The product has already changed. Two good changes can clash, which is why the base is checked.

## Now change it

Now do the same for your own task, from a clean product.

1. Reset the product to the baseline and clear the earlier results:
   ```bash
   rm -rf product decisions base.json card.html
   cp -R "$REPO"/workshops/software-factories-masterclass/book/ready/ch07/product product
   ```

2. Integrate the attempt that was accepted for your task, and draw the card:
   ```bash
   python integrate.py --record-base
   python integrate.py tasks/b-limit-currencies.json attempts/mine
   python show_card.py --offline
   ```

   You see `INTEGRATED`, then `wrote card.html`. Open `card.html`: the market card shows exactly the number of currencies you asked for.

## You are done when

From inside `my-factory`, with your environment active, this prints `ch07 OK`:

```bash
grep -q INTEGRATED decisions/integration.json \
 && python show_card.py --offline \
 && python - <<'EOF'
import json, re
limit = json.load(open("tasks/b-limit-currencies.json"))["limit"]
rows = set(re.findall(r"EUR[A-Z]{3}", open("card.html").read()))
assert len(rows) == limit, rows
print("ch7 OK: the card shows", limit, "currencies")
EOF
```

At the start of this chapter there is no decision and no card, so it fails. It passes only when your change is integrated and the card shows your number of currencies.

## If it fails

- `REFUSED: stale base`: you integrated already. Run the reset in step 1 and start again.
- `base.json` not found: run `python integrate.py --record-base` first.
