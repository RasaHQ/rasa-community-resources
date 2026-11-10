> **22 October revision:** Start with [the participant guide](../PARTICIPANT-GUIDE.md) for the three-hour route, current API distinctions, and platform requirements. These chapters are reference exercises; their checks do not certify the complete voice-to-build-to-voice journey.

# Chapter 6: The gates and the decision

A traveler sees a daily exchange rate labeled as live and plans a purchase around it. The card looks plausible, but its claim is wrong. You need a gate that rejects it and says which requirement failed.

Time: about 15 minutes after installation. You need: Chapter 4, or copy the ready folder for this chapter. This chapter needs macOS for the gate (see the README). Chapter 5 shows a builder using the OpenAI Agents API. Here you use the scripted builder, which works offline.

You're done when `ch06 OK` confirms that your attempt is accepted and the attempt that ignores your limit is rejected by the named check.

If you get stuck, use [the ready folder](ready/ch06) and follow **Get the ready folder** below in a fresh work folder.

## Words used in this chapter

- **Attempt:** one try at the task, kept as a folder with only the files it changed.
- **Gate:** one check an attempt must pass before the next one runs.
- **Decision:** ACCEPT (every gate passed), REJECT (a gate failed, and the decision names it) or could not run (a problem with the machine).
- **Exit code:** the number a program gives back when it ends. 0 is success, 1 is rejected, 2 is could not run.

## Get the ready folder

Every chapter has a finished, working folder, so you don't need the earlier chapters' folders. Copy the one for this chapter into `~/factory-work` (it creates a new folder there, `my-factory-ch06`, and refuses to overwrite an existing one), then set up Python once:

```bash
export PACK=~/rasa-community-resources/workshops/software-factories-masterclass   # after a clone
# after unzipping, use this line instead: export PACK=/path/to/the/unzipped/software-factories-masterclass
mkdir -p ~/factory-work && cd ~/factory-work
[ -e my-factory-ch06 ] && echo "my-factory-ch06 already exists: use it, or move it away first" || cp -R "$PACK"/book/ready/ch06 my-factory-ch06
```

```bash
cd my-factory-ch06
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.6 httpx==0.28.1
```
## See how it works


1. Open `run_a6.py` and read its first lines. The gates run in this order:
   1. The fingerprints of the protected files must match the task. If not, nothing runs (exit code 2, could not run).
   2. The attempt must hold no copy of a protected file and no symbolic link. A copy of the tests would be an edit of the tests.
   3. The attempt may change only the allowed paths.
   4. The protected tests must pass, and the run must end with its own closing lines.
2. Judge a good attempt and a bad one for the first task:
   ```bash
   python run_a6.py tasks/a6-market-watchlist.json candidates/market-good
   python run_a6.py tasks/a6-market-watchlist.json candidates/market-shows-live
   ```

   The first prints `ACCEPT`. The second prints `REJECT` and names the failing checks, for example `test_k3_...`: it showed a daily rate as a live quote.
3. Judge the attempt that edits the tests:
   ```bash
   python run_a6.py tasks/a6-market-watchlist.json candidates/market-edits-suite
   ```

   You see `REJECT - protected file edited`. It was stopped at gate 2, before any test ran.

## Now change it

Set the currency limit you want, ask the builder for an attempt, then run both the good and bad attempts through the gates.

The ready folder uses a limit of 2. If you chose a different limit in Chapter 3 (1 or 3), set it first by replacing the 2 below with your number. This also makes the builder's attempt again for the new number:
   ```bash
   python set_limit.py 2
   ```

1. Run the scripted builder. It reads the limit from your task and writes an attempt, with no model call:
   ```bash
   python scripted_builder.py tasks/b-limit-currencies.json attempts/mine
   ```

   (The live builder from Chapter 5 does the same job with the OpenAI Agents API. This offline builder lets everyone finish this chapter without a key.)
2. Judge your attempt, and the bad attempt that ignores the limit:
   ```bash
   python run_a6.py tasks/b-limit-currencies.json attempts/mine
   python run_a6.py tasks/b-limit-currencies.json attempts/b-ignores-limit
   ```

   Yours prints `ACCEPT`. The other prints `REJECT` and names `test_b1_...`: it showed more currencies than your limit. Read that name to find the requirement the attempt broke.

## You are done when

From inside `my-factory-ch06`, with your environment active, this prints a line that starts with `ch06 OK`:

```bash
python - <<'EOF'
import subprocess, sys
def gate(attempt):
    return subprocess.run([sys.executable, "run_a6.py", "tasks/b-limit-currencies.json", attempt], capture_output=True, text=True)
good = gate("attempts/mine")
assert good.returncode == 0 and good.stdout.startswith("ACCEPT"), good.stdout + good.stderr
bad = gate("attempts/b-ignores-limit")
assert bad.returncode == 1 and bad.stdout.startswith("REJECT") and "test_b1" in bad.stdout, bad.stdout + bad.stderr
print("ch06 OK: your attempt is accepted, and the attempt that ignores the limit is rejected by test_b1")
EOF
```

It passes only when your attempt is accepted (exit code 0) and the attempt that ignores the limit is rejected (exit code 1) by `test_b1`. A crash or a setup problem does not count as a rejection. At the start of this chapter there is no attempt for your task, so it fails.

## If it fails

- `could not run: this check needs macOS`: the gate needs a Mac. Pair with someone on a Mac, or follow along on screen.
- `could not run: the protected file ... does not match`: the fingerprints don't match the files. Copy the ready folder again.
- `Set a limit from 1 to 3`: run `python set_limit.py 2` first.

## Good to know

A setup failure stops the gate before it can judge the change. Keep that result separate from a REJECT that names a failed product check.

## What you just learned

You saw the gates accept your attempt and reject an attempt that ignored the currency limit. The named failure tells you which requirement to inspect before asking the builder for another attempt.

Next: [put an accepted change into the product](07-integrate-and-run-it-dark.md).
