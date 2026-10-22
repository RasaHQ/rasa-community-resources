# Chapter 3: A factory starts with a task

**Goal:** see how a factory is told what to build, then change the task yourself.

**You need first:** Chapter 0 (the repository cloned), Python 3.12 and uv.

## Words used in this chapter

- **Factory:** a set of steps that turns a written request into a checked change, the same way every time.
- **Task:** the written request, plus the list of files the builder may change.
- **Allowed paths:** the only places the builder may change. Anything else is refused.
- **Baseline:** the product as it is before the change, with no market card yet.
- **Limit:** in this chapter, the number of currencies your market card may show.

## Get the ready folder

Every chapter has a finished, working folder. Copy the one for this chapter next to your clone, then set up Python once:

```bash
export REPO=~/rasa-community-resources   # the folder where you cloned the repository
cp -R "$REPO"/workshops/software-factories-masterclass/book/ready/ch03 my-factory
```

```bash
cd my-factory
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.4 httpx
```
## See how it works


1. Look at the task. It is a plain text file:
   ```bash
   cat tasks/a6-market-watchlist.json
   ```

   It holds the request in words, the **allowed paths** (two places) and the fingerprints of the files that will judge the work. Open `tasks/a6-market-watchlist.json` and read each field.
2. Look at the baseline. This is the product with no market card yet:
   ```bash
   cat product/briefing/market_card.py
   ```

   It has one function, `market_card`, and it says the card isn't built yet. A builder's job is to fill it in.
3. See a finished factory judge an attempt for this task. The attempt in `candidates/market-good` is a good one:
   ```bash
   python run_a6.py tasks/a6-market-watchlist.json candidates/market-good
   ```

   You see `ACCEPT - protected acceptance passed (Ran 14 tests ...)`. You didn't write any code. The task asked, an attempt answered and the gates decided.

## Now change it

Your task is a variation of the first one: the market card, but limited to a number of currencies. The limit is yours to choose.

1. Open `tasks/b-limit-currencies.json`. The line `"limit": null` is what you ask for. Change `null` to a number from 1 to 3, for example 2, and save. That is the whole change: you wrote no code. In a factory you ask for a change by changing the task.
   If you prefer to do it from the terminal, this sets the limit to 2:
   ```bash
   python - <<'EOF'
   import json
   from pathlib import Path
   p = Path('tasks/b-limit-currencies.json')
   t = json.loads(p.read_text())
   t['limit'] = 2
   p.write_text(json.dumps(t, indent=2) + '\n')
   EOF
   ```


## You are done when

From inside `my-factory`, with your environment active, this prints `ch03 OK`:

```bash
python -c "import json, pathlib; t = json.load(open('tasks/b-limit-currencies.json')); assert isinstance(t['limit'], int) and 1 <= t['limit'] <= 3; assert 'limit' in t['request']; assert all(pathlib.Path(p).exists() for p in t['allowed_paths']); print('ch3 OK')"
```

At the start of this chapter `limit` is empty, so it fails.

## If it fails

- `limit` still says `null`: set it to 1, 2 or 3 and save the file.
- `No such file`: run the command from inside `my-factory`.
