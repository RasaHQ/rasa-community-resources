# Chapter 7: Integrate and run it dark

**Goal:** finish the factory with integration, then run the whole loop so that an accepted change goes into your product and the market card is drawn, without anyone reading the change.

**You need first:** Chapter 6. Start from your `my-factory`, or copy `checkpoints/ch6` (see Chapter 3 for how). In a terminal, move into `my-factory` and activate your environment first:

```
cd my-factory
source .venv/bin/activate
```


**You build:** the integration step, `integrate.py`, and a small script, `show_card.py`, that draws the card from your product.

## Words used in this chapter
- **Integration:** putting an accepted change into the product.
- **Stale base:** the product has changed since the attempt was made, so the attempt was judged against something that is no longer there.
- **Replay:** running the earlier checks again on the product after the change went in.
- **Run it dark:** let the tests, and not a person reading each change, decide.

## What integration does
1. It asks the gate. If the gate doesn't say ACCEPT, nothing goes in.
2. It refuses a stale base. Two attempts can each pass alone, and the second can quietly undo the first. So the product must be exactly the one the attempt was made against.
3. It copies the allowed files in.
4. It replays the protected tests on the integrated product. If they fail, the change comes out again.
5. It writes the decision with its evidence.

## Steps

1. Create the integration step, `integrate.py`:
```python
#!/usr/bin/env python3
"""Integration: put an accepted change into the product, then replay the checks on the result.

    python integrate.py --record-base                                         remember the product you start from
    python integrate.py tasks/a6-market-watchlist.json candidates/market-good integrate a candidate
Exit 0 integrated, 1 refused, 2 could not run.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRACKED = "product/briefing/market_card.py"


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv):
    if argv == ["--record-base"]:
        (ROOT / "base.json").write_text(json.dumps({TRACKED: fingerprint(ROOT / TRACKED)}, indent=2) + "\n")
        print("recorded the base product")
        return 0
    task_path, candidate = argv
    base = json.loads((ROOT / "base.json").read_text())
    # 1. the gate must say ACCEPT
    gate = subprocess.run([sys.executable, str(ROOT / "run_a6.py"), task_path, candidate], capture_output=True, text=True)
    if gate.returncode != 0:
        print("REFUSED: the gate did not accept this change:", gate.stdout.strip()[:160])
        return 1
    # 2. a stale base: the product must still be the one the change was made against
    if fingerprint(ROOT / TRACKED) != base[TRACKED]:
        print("REFUSED: stale base. The product has changed since this change was made.")
        return 1
    # 3. copy the allowed files in, then replay the checks on the integrated product
    task = json.loads((ROOT / task_path).read_text())
    for rel in task["allowed_paths"]:
        src = Path(candidate) / rel
        if src.is_dir():
            shutil.copytree(src, ROOT / rel, dirs_exist_ok=True)
        elif src.exists():
            shutil.copy2(src, ROOT / rel)
    replay = subprocess.run([sys.executable, "-I", str(ROOT / task["acceptance"]["path"])], capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "PRODUCT_PROJECT": str(ROOT / "product"), "PYTHONDONTWRITEBYTECODE": "1"})
    ok = replay.returncode == 0 and replay.stderr.strip().splitlines()[-1] == "OK"
    record = {"decision": "INTEGRATED" if ok else "ROLLED BACK", "candidate": str(candidate),
              "protected_suite_sha256": fingerprint(ROOT / task["acceptance"]["path"]), "tracked_file_sha256": fingerprint(ROOT / TRACKED)}
    (ROOT / "decisions").mkdir(exist_ok=True)
    (ROOT / "decisions" / "integration.json").write_text(json.dumps(record, indent=2) + "\n")
    print(record["decision"], "-", "the checks replayed on the integrated product" if ok else "the replay failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

2. Create the script that draws the card, `show_card.py`. It uses a recorded answer from the exchange-rate source, so it needs no network:
```python
#!/usr/bin/env python3
"""Draw the market card from your product, using a recorded answer from the ECB, and write card.html.

    python show_card.py --offline
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent / "product"))

from zeo_core.adapters.widget_html import render_snapshot_html
from zeo_core.contracts.ui.widgets import CardState
from zeo_core.integrations.briefing_sources import PublicBriefingSources
from zeo_core.integrations.briefing_sources import http as H

from briefing.market_card import market_card

NOW = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)
CSV = ("FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
       "D,USD,EUR,SP00,A,2026-10-20,1.1631\nD,USD,EUR,SP00,A,2026-10-21,1.1650\n"
       "D,GBP,EUR,SP00,A,2026-10-20,0.8723\nD,GBP,EUR,SP00,A,2026-10-21,0.8700\n")


def main():
    if "--offline" not in sys.argv:
        print("Use --offline: this chapter draws the card from a recorded answer, so it needs no network.")
        return 2
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=CSV, headers={"Content-Type": "text/csv"}))
    http = H.PublicSourceHTTP(transport=transport, clock=lambda: NOW, monotonic=lambda: 1000.0, sleep=lambda s: None)
    sources = PublicBriefingSources(http, clock=lambda: NOW)
    ref = market_card(sources, ["USD", "GBP"])
    card = CardState(widget_id="market-watchlist", component="market_watchlist", revision=1, request_id="r1", replaced=False, data_ref=ref)
    Path("card.html").write_text(render_snapshot_html([card], document=True, title="Market watchlist"))
    print("wrote card.html: open it in a browser")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

3. Remember the product you start from:
```
python integrate.py --record-base
```

   You see: `recorded the base product`.
4. Try to integrate a bad attempt. It is stopped at the gate:
```
python integrate.py tasks/a6-market-watchlist.json candidates/market-shows-live
```

   You see: `REFUSED: the gate did not accept this change`.
5. Integrate the good attempt:
```
python integrate.py tasks/a6-market-watchlist.json candidates/market-good
```

   You see: `INTEGRATED - the checks replayed on the integrated product`. The file `decisions/integration.json` records the decision, the fingerprint of the protected tests and the fingerprint of the changed file.
6. Draw the card, and open `card.html` in a browser:
```
python show_card.py --offline
```

   You see the market watchlist card with its label, its publication day and the change worked out from two days.
7. Try to integrate the same attempt again. The product has already changed, so this is a stale base:
```
python integrate.py tasks/a6-market-watchlist.json candidates/market-good
```

   You see: `REFUSED: stale base`.

## You are done when
From inside `my-factory`, after step 6, with your environment active, this prints `ch7 OK`:
```
grep -q INTEGRATED decisions/integration.json \
 && python show_card.py --offline \
 && grep -q "daily reference rate, not a live quote" card.html \
 && echo "ch7 OK"
```

It passes only when the decision says INTEGRATED and the card your product draws carries its honest label. At the start of this chapter there is no decision file and no `show_card.py`, so it fails.

## What about the full agent?
In your `my-factory`, the product is a small stand-in for the briefing agent. In the full agent from Chapter 0, the same change goes in through the same factory, and the agent restarts with the fourth card. That wiring lives in the briefing example and is covered there.

## Checkpoint
`checkpoints/ch7/`: your finished factory, as it stands after step 7, with the change integrated and `card.html` drawn. Compare it with the finished factory in `$REPO/workshops/software-factories-masterclass/factory/a6-market-watchlist/`.

## If it fails
- `REFUSED: stale base`: you already integrated. Copy `checkpoints/ch6` into a fresh folder and start step 3 again.
- `base.json` not found: run step 3 first.
