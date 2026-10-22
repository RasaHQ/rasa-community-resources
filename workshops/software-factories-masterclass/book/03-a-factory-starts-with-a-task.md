# Chapter 3: A factory starts with a task

**Goal:** see how a factory is told what to build, then change the task yourself and watch the factory accept the result.

**You need first:** Chapter 0 (the repository cloned), Python 3.12 and uv.

## Words used in this chapter

- **Factory:** a set of steps that turns a written request into a checked change, the same way every time.
- **Task:** the written request, plus the list of files the builder may change.
- **Allowed paths:** the only places the builder may change. Anything else is refused.
- **Baseline:** the product as it is before the change, with no market card yet.
- **Builder:** the coding agent that makes the change. In Chapter 5 it runs on the OpenAI Agents API. Here you use the **scripted builder**, a stand-in that needs no model and no key.
- **Limit:** in this chapter, the number of currencies your market card may show.

## Get the ready folder

Every chapter has a finished, working folder, so you don't need the earlier chapters' folders. Copy the one for this chapter next to your clone (it creates a new folder, `my-factory-ch03`), then set up Python once:

```bash
export REPO=~/rasa-community-resources   # the folder where you cloned the repository
mkdir -p ~/factory-work && cd ~/factory-work
[ -e my-factory-ch03 ] && echo "my-factory-ch03 already exists: use it, or move it away first" || cp -R "$REPO"/workshops/software-factories-masterclass/book/ready/ch03 my-factory-ch03
```

```bash
cd my-factory-ch03
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.4 httpx==0.28.1
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

Your task is a variation of the first one: the market card, but limited to a number of currencies. The tests for it are already written and locked (Chapter 4 shows how). You choose the limit, the builder makes an attempt and the gates decide. You write no code.

1. Choose a limit from 1 to 3 and set it in your task. This sets 2:
   ```bash
   python set_limit.py 2
   ```

   (You can also open `tasks/b-limit-currencies.json` and change the line `"limit": null` yourself.)
2. Ask the scripted builder for an attempt. It reads your task, writes only the allowed files and never sees the tests:
   ```bash
   python scripted_builder.py tasks/b-limit-currencies.json attempts/mine
   ```

   (The live builder from Chapter 5 does the same job with the OpenAI Agents API. This offline builder lets everyone finish without a key.)
3. Let the gates decide:
   ```bash
   python run_a6.py tasks/b-limit-currencies.json attempts/mine
   ```

   You see `ACCEPT - protected acceptance passed (Ran 6 tests ...)`.

## You are done when

From inside `my-factory-ch03`, with your environment active, this prints a line that starts with `ch03 OK`:

```bash
python - <<'EOF'
import json, subprocess, sys
t = json.load(open("tasks/b-limit-currencies.json"))
assert isinstance(t["limit"], int) and 1 <= t["limit"] <= 3, "set your limit first"
r = subprocess.run([sys.executable, "run_a6.py", "tasks/b-limit-currencies.json", "attempts/mine"], capture_output=True, text=True)
assert r.returncode == 0 and r.stdout.startswith("ACCEPT"), r.stdout + r.stderr
print("ch03 OK: the builder's attempt for your task is accepted, with a limit of", t["limit"])
EOF
```

It passes only when your limit is set and the builder's attempt for your task is accepted. At the start of this chapter `limit` is empty and there is no attempt, so it fails.

## If it fails

- `limit` still says `null`: run step 1.
- `No such file`: run the command from inside `my-factory-ch03`.
- `could not run: the protected file ... does not match`: you changed a file under `acceptance/`. Copy the ready folder again.
