# Chapter 6: The gates and the decision

**Goal:** see how an attempt is judged, then have the builder make an attempt for your task and watch the gates decide.

**You need first:** Chapter 4, or copy the ready folder for this chapter. Chapter 5 builds the live builder on the OpenAI Agents API. Here you use the scripted builder, which needs no model call, so this chapter works offline.

## Words used in this chapter

- **Attempt:** one try at the task, kept as a folder with only the files it changed. (The code calls it a candidate.)
- **Gate:** one check an attempt must pass before the next one runs.
- **Decision:** ACCEPT (every gate passed), REJECT (a gate failed, and the decision names it) or could not run (a problem with the machine).
- **Exit code:** the number a program gives back when it ends. 0 is success, 1 is rejected, 2 is could not run.
- **Scripted builder:** a stand-in for the builder from Chapter 5. It writes an attempt without any model.

## Get the ready folder

Every chapter has a finished, working folder. Copy the one for this chapter next to your clone, then set up Python once:

```bash
export REPO=~/rasa-community-resources   # the folder where you cloned the repository
cp -R "$REPO"/workshops/software-factories-masterclass/book/ready/ch06 my-factory
```

```bash
cd my-factory
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.4 httpx
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

Now ask for the change: have a builder make an attempt for your task, and let the gates decide.

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

   Yours prints `ACCEPT`. The other prints `REJECT` and names `test_b1_...`: it showed more currencies than your limit. You wrote no code, and the decision isn't yours: the gates made it.

## You are done when

From inside `my-factory`, with your environment active, this prints `ch06 OK`:

```bash
T=tasks/b-limit-currencies.json
python run_a6.py $T attempts/mine > /dev/null \
 && ! python run_a6.py $T attempts/b-ignores-limit > /dev/null \
 && echo "ch6 OK"
```

At the start of this chapter there is no attempt for your task, so it fails. It passes only when your attempt is accepted and the bad one is rejected.

## If it fails

- `could not run: the protected file ... does not match`: the fingerprints don't match the files. Lock them again (Chapter 4).
- `Set a limit from 1 to 3`: set the limit in your task first (Chapter 3).
