# Chapter 4: Acceptance before code

**Goal:** write the protected acceptance suite for the market card before any candidate exists, and see it fail on the baseline for the right reasons.

**You need first:** Chapter 3.

**You build:** the hidden suite and its child runner, using `../factory/a6-market-watchlist/` as the worked example, then the pins that bind them to the task.

## Steps
Status: outline. The steps write the checks first (rows, publication day, labels, computed change, failure, garbage input, no network), run them against the baseline and pin them.

## You are done when
Every pin in the task matches its protected file (the suite and its child runner), and, from `factory/a6-market-watchlist/`, `python run_a6.py tasks/a6-market-watchlist.json baseline` rejects the baseline, and the failing checks are the ones you wrote for the missing card. This chapter needs the A6 task and its factory folder to be in the repository first.

## Checkpoint
`checkpoints/ch4/`: the factory with a task and its protected acceptance.
