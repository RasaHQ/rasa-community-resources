# Chapter 4: Write the task and its acceptance first

**Goal:** write the market card task and its protected acceptance suite before any code exists, and see the suite fail on the baseline for the right reasons.

**You need first:** Chapter 3.

**You build:** the task file (prompt, allowed paths, pins) and a hidden suite, using `../factory/a6-market-watchlist/` as the worked example.

## Steps
Status: outline. The steps write the checks first (rows, publication day, labels, computed change, failure, garbage input), then run them against the baseline.

## You are done when
`python run_a6.py tasks/a6-market-watchlist.json baseline` rejects the baseline, and the failing checks are the ones you wrote for the missing card.

## Checkpoint
`checkpoints/ch4/`.
