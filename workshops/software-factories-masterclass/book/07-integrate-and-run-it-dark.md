# Chapter 7: Integrate and run it dark

**Goal:** see an accepted change go into the product, then do it for your own task, with nobody reading the change.

**You need first:** Chapter 6, or copy the ready folder for this chapter. This chapter needs macOS for the gate (see the README).

## Words used in this chapter

- **Integration:** putting an accepted change into the product.
- **Stale base:** the product changed after the attempt was made, so the attempt was judged against something that is gone.
- **Replay:** running the checks again on the product after the change went in. If they fail, the change comes out again.
- **Run it dark:** let the tests decide, with no person reading each change.

## Get the ready folder

Every chapter has a finished, working folder, so you don't need the earlier chapters' folders. Copy the one for this chapter into `~/factory-work` (it creates a new folder there, `my-factory-ch07`, and refuses to overwrite an existing one), then set up Python once:

```bash
export REPO=~/rasa-community-resources   # the folder where you cloned the repository
mkdir -p ~/factory-work && cd ~/factory-work
[ -e my-factory-ch07 ] && echo "my-factory-ch07 already exists: use it, or move it away first" || cp -R "$REPO"/workshops/software-factories-masterclass/book/ready/ch07 my-factory-ch07
```

```bash
cd my-factory-ch07
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.6 httpx==0.28.1
```
## See how it works


1. Open `integrate.py` and read its first lines. Integration does five things:
   1. It asks the gate. If the gate doesn't say ACCEPT, nothing goes in.
   2. It refuses a stale base: the product must be exactly the one the attempt was made against.
   3. It copies the allowed files in.
   4. It replays the protected tests on the integrated product. If they fail, it puts every file back as it was.
   5. It writes the decision with its evidence.
2. Integrate the good attempt for the first task into a copy of the product, and draw the card:
   ```bash
   python integrate.py --record-base
   python integrate.py tasks/a6-market-watchlist.json candidates/market-good
   python show_card.py --offline
   ```

   You see `recorded the base product`, then `INTEGRATED - the checks replayed on the integrated product`, then `wrote card.html`. Open `card.html` in a browser: the market card with four currencies. The page is titled "sample numbers, not live", because `show_card.py` draws it from a small bundled sample of exchange-rate data so that it works offline. The numbers are made up for the exercise. They aren't real rates.
3. Try the same integration again:
   ```bash
   python integrate.py tasks/a6-market-watchlist.json candidates/market-good
   ```

   You see `REFUSED: stale base`. The product has already changed. Two good changes can clash, which is why the base is checked.

## Now change it

Now do the same for your own task, from a clean product. Use the same terminal as before, so that `REPO` is still set (if it isn't, run `export REPO=~/rasa-community-resources` again).

The ready folder uses a limit of 2. If you chose a different limit in Chapter 3 (1 or 3), set it first by replacing the 2 below with your number. This also makes the builder's attempt again for the new number:
   ```bash
   python set_limit.py 2
   ```

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

   You see `INTEGRATED`, then `wrote card.html`. Open `card.html`: the market card shows exactly the number of currencies you asked for, and the page says it uses sample numbers.

## You are done when

From inside `my-factory-ch07`, with your environment active, this prints a line that starts with `ch07 OK`:

```bash
grep -q INTEGRATED decisions/integration.json \
 && python show_card.py --offline \
 && python - <<'EOF'
import json, re
limit = json.load(open("tasks/b-limit-currencies.json"))["limit"]
page = open("card.html").read()
rows = set(re.findall(r"EUR[A-Z]{3}", page))
assert len(rows) == limit, rows
assert "sample numbers, not live" in page
print("ch07 OK: the card shows", limit, "currencies and says it uses sample numbers")
EOF
```

It passes only when your change is integrated and the card shows your number of currencies. At the start of this chapter there is no decision and no card, so it fails.

## If it fails

- `could not run: this check needs macOS`: the gate needs a Mac. Pair with someone on a Mac, or follow along on screen.
- `REFUSED: stale base`: you integrated already. Run the reset in step 1 and start again.
- `could not run: there is no base.json`: run `python integrate.py --record-base` first.
