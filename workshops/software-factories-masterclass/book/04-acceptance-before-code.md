# Chapter 4: Acceptance before code

**Goal:** see the tests that judge a change, written before any work, lock them for your own task and watch the factory accept the builder's attempt.

**You need first:** Chapter 3, or copy the ready folder for this chapter.

## Words used in this chapter

- **Test:** a small program that checks another program. **Acceptance test:** checks that what you asked for was built.
- **Protected tests:** the acceptance tests the builder never sees and can't change.
- **Fingerprint (hash):** a short code made from a file. Change one letter and it changes.
- **Sandbox:** a safety box from the operating system that blocks the network. It uses `sandbox-exec`, which comes with macOS. On another system the network check fails by design: read this chapter beside its ready folder.

## Get the ready folder

Every chapter has a finished, working folder, so you don't need the earlier chapters' folders. Copy the one for this chapter into `~/factory-work` (it creates a new folder there, `my-factory-ch04`, and refuses to overwrite an existing one), then set up Python once:

```bash
export REPO=~/rasa-community-resources   # the folder where you cloned the repository
mkdir -p ~/factory-work && cd ~/factory-work
[ -e my-factory-ch04 ] && echo "my-factory-ch04 already exists: use it, or move it away first" || cp -R "$REPO"/workshops/software-factories-masterclass/book/ready/ch04 my-factory-ch04
```

```bash
cd my-factory-ch04
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.6 httpx==0.28.1
```
## See how it works


1. Run the tests for the first task against the baseline. They fail, because the card isn't built:
   ```bash
   python run_a6.py tasks/a6-market-watchlist.json baseline
   ```

   You see `REJECT` and a list of failing checks such as `test_k1_...`. Each fails for the right reason: there is no card yet.
2. Read the top of the tests. Open `acceptance/a6_market_watchlist.py`: the first lines list ten checks in plain words (the rows, the publication day, the labels, the change since yesterday, the failure case and more).
3. Read what runs the attempt. Open `acceptance/a6_child.py`: it runs the attempt's `market_card` with a recorded answer from the exchange-rate source, in a safe child process, and prints only the card as data. It decides nothing.
4. Read your own task's tests. Open `acceptance/b_limit_currencies.py`: six checks, written for you. The limit comes from your task file (`limit` in `tasks/b-limit-currencies.json`), and the tests never change.

## Now change it

Your task's tests are written. You lock them, so that nobody can change them without the fingerprint showing it, and then the factory judges the builder's attempt against them.

The ready folder uses a limit of 2. If you chose a different limit in Chapter 3 (1 or 3), set it first by replacing the 2 below with your number. This also makes the builder's attempt again for the new number:
   ```bash
   python set_limit.py 2
   ```

1. Run your task's tests against the baseline. They fail, because the card isn't built:
   ```bash
   PRODUCT_PROJECT=$PWD/product python acceptance/b_limit_currencies.py
   ```

   You see `FAILED` and `test_b1_four_currencies_show_at_most_the_limit` among five failures, one for each card check. The sixth check, the network one, passes.
2. Lock the tests. This writes the fingerprint of each protected file into your task:
   ```bash
   python - <<'EOF'
   import hashlib, json
   from pathlib import Path
   p = Path("tasks/b-limit-currencies.json")
   t = json.loads(p.read_text())
   t["acceptance"]["sha256"] = hashlib.sha256(Path(t["acceptance"]["path"]).read_bytes()).hexdigest()
   for item in t["support"]:
       item["sha256"] = hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
   p.write_text(json.dumps(t, indent=2) + "\n")
   print("pinned")
   EOF
   ```

   You see `pinned`. Now the task knows exactly which tests judge the work.
3. Ask the scripted builder for an attempt, and let the gates decide:
   ```bash
   python scripted_builder.py tasks/b-limit-currencies.json attempts/mine
   python run_a6.py tasks/b-limit-currencies.json attempts/mine
   ```

   You see `ACCEPT - protected acceptance passed (Ran 6 tests ...)`.

## You are done when

From inside `my-factory-ch04`, with your environment active, this prints a line that starts with `ch04 OK`:

```bash
python - <<'EOF'
import hashlib, json, os, re, subprocess, sys
from pathlib import Path
t = json.loads(Path("tasks/b-limit-currencies.json").read_text())
for item in [t["acceptance"], *t["support"]]:
    assert hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"], item["path"]
env = {"PATH": "/usr/bin:/bin", "PRODUCT_PROJECT": os.path.abspath("product")}
r = subprocess.run([sys.executable, "-I", t["acceptance"]["path"]], capture_output=True, text=True, env=env)
failing = set(re.findall(r"^FAIL: (test_b\d)", r.stderr, re.M))
lines = r.stderr.strip().splitlines()
assert r.returncode == 1 and "Ran 6 tests" in r.stderr and lines[-1] == "FAILED (failures=5)" and "ERROR:" not in r.stderr, "setup problem or unexpected result: " + r.stderr[-300:]
assert failing == {"test_b1", "test_b2", "test_b3", "test_b4", "test_b5"}, "unexpected failures: " + str(failing)
g = subprocess.run([sys.executable, "run_a6.py", "tasks/b-limit-currencies.json", "attempts/mine"], capture_output=True, text=True)
assert g.returncode == 0 and g.stdout.startswith("ACCEPT"), g.stdout + g.stderr
print("ch04 OK: the tests fail on the baseline for the right reasons, and the builder's attempt is accepted")
EOF
```

It passes only when the fingerprints match, the tests fail on the baseline for the five card checks (not for a setup problem), and the builder's attempt is accepted. At the start of this chapter the fingerprints are empty, so it fails.

## If it fails

- `sandbox-exec: command not found`: the network check needs macOS. Read this chapter beside `book/ready/ch04`.
- `No module named zeo_core`: activate the environment and install `zeocore==0.35.6`.
- Fingerprint mismatch: you changed a protected file after locking. Lock again.
