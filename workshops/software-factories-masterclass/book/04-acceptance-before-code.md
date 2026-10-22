# Chapter 4: Acceptance before code

**Goal:** see the tests that judge a change, written before any work, and lock the tests for your own task.

**You need first:** Chapter 3, or copy the ready folder for this chapter.

## Words used in this chapter

- **Test:** a small program that checks another program. **Acceptance test:** checks that what you asked for was built.
- **Protected tests:** the acceptance tests the builder never sees and can't change.
- **Fingerprint (hash):** a short code made from a file. Change one letter and it changes.
- **Sandbox:** a safety box from the operating system that blocks the network. It uses `sandbox-exec`, which comes with macOS. On another system the network check fails by design: read this chapter beside its ready folder.

## Get the ready folder

Every chapter has a finished, working folder. Copy the one for this chapter next to your clone, then set up Python once:

```bash
export REPO=~/rasa-community-resources   # the folder where you cloned the repository
cp -R "$REPO"/workshops/software-factories-masterclass/book/ready/ch04 my-factory-ch04
```

```bash
cd my-factory-ch04
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install zeocore==0.35.4 httpx==0.28.1
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

Your task's tests are written. You lock them, so that nobody can change them without the fingerprint showing it.

1. Run your task's tests against the baseline. They fail, because the card isn't built:
   ```bash
   PRODUCT_PROJECT=$PWD/product python acceptance/b_limit_currencies.py
   ```

   You see `FAILED` and `test_b1_four_currencies_show_at_most_the_limit` among the failures.
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

## You are done when

From inside `my-factory-ch04`, with your environment active, this prints a line that starts with `ch04 OK`:

```bash
python - <<'EOF'
import hashlib, json, os, subprocess, sys
from pathlib import Path
t = json.loads(Path("tasks/b-limit-currencies.json").read_text())
for item in [t["acceptance"], *t["support"]]:
    assert hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"], item["path"]
r = subprocess.run([sys.executable, "-I", t["acceptance"]["path"]], capture_output=True, text=True,
                   env={"PATH": "/usr/bin:/bin", "PRODUCT_PROJECT": os.path.abspath("product")})
assert r.returncode != 0 and "FAILED" in r.stderr and "test_b1" in r.stderr, r.stderr[-300:]
print("ch04 OK: the fingerprints match and the tests fail on the baseline")
EOF
```

At the start of this chapter the fingerprints in your task are empty, so it fails.

## If it fails

- `sandbox-exec: command not found`: the network check needs macOS. Read this chapter beside `book/ready/ch04`.
- `No module named zeo_core`: activate the environment and install `zeocore==0.35.4`.
- Fingerprint mismatch: you changed a protected file after locking. Lock again.
