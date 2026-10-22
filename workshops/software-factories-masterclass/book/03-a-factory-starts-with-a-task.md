> **22 October revision:** Start with [the participant guide](../PARTICIPANT-GUIDE.md) for the three-hour route, current API distinctions, and platform requirements. These chapters are reference exercises; their checks do not certify the complete voice-to-build-to-voice journey.

# Chapter 3: A factory starts with a task

A team asks a coding agent for a currency card and gets one that looks right, but nobody wrote down what "right" meant. A factory starts with a written request and a list of the files the builder may change. In about 25 minutes you'll set a limit on a currency card and watch a factory accept the result without you writing any code.

Time: about 25 minutes. You need: a Mac (the check runs in a macOS sandbox), Python 3.12, uv and the repository cloned in Chapter 0. No key or account.

You're done when the check at the end prints a line that starts with `ch03 OK`. If you get stuck, start again from `book/ready/ch03` in a fresh folder.

## Words used in this chapter

- **Factory:** a set of steps that turns a written request into a checked change, the same way every time.
- **Task:** the written request, plus the list of files the builder may change.
- **Allowed paths:** the only places the builder may change. Anything else is refused.
- **Builder:** the coding agent that makes the change. In Chapter 5 it runs on the OpenAI Agents API. Here you use the **scripted builder**, a stand-in that needs no model and no key.

## Get the ready folder

Every chapter has a finished, working folder, so you don't need the earlier chapters' folders. Copy the one for this chapter into `~/factory-work` (it creates a new folder there, `my-factory-ch03`, and refuses to overwrite an existing one), then set up Python once:

```bash
export PACK=/absolute/path/to/software-factories-masterclass   # the unzipped workshop root
mkdir -p ~/factory-work && cd ~/factory-work
[ -e my-factory-ch03 ] && echo "my-factory-ch03 already exists: use it, or move it away first" || cp -R "$PACK"/book/ready/ch03 my-factory-ch03
```

```bash
cd my-factory-ch03
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.6 httpx==0.28.1
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

Your task is a variation of the first one: the market card, limited to the number of currencies you choose. The tests for it are already written and locked (Chapter 4 shows how). You choose the limit, the builder makes an attempt and the gates decide. You write no code.

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

- `could not run: this check needs macOS`: the gate needs a Mac. Pair with someone on a Mac, or follow along on screen.
- `limit` still says `null`: run step 1.
- `No such file`: run the command from inside `my-factory-ch03`.
- `could not run: the protected file ... does not match`: you changed a file under `acceptance/`. Copy the ready folder again.

## What you just learned

A factory works from a written task: the request, the files the builder may change, and the fingerprints of the files that judge the work. You changed the task, and the gates decided without you reading the code.

Next: [Chapter 4](04-acceptance-before-code.md) shows the tests that judge the change, and how they are locked before any work starts.
