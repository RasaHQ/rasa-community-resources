# Task A6: the market watchlist card (the factory builds the fourth card)

The task, the prepared platform and the protected acceptance for the second screen of the class. The files here
extend the factory in `workshops/software-factories-masterclass/factory`; they are not a second factory.

## What the builder gets
The prompt is the `request` in `tasks/a6-market-watchlist.json`. The platform is already built and accepted:
zeocore's card contracts, renderer and four source readers (the ECB daily reference-rate reader included), the
briefing service with three cards, the launcher and the builder's instructions (`builder/AGENTS-a6.md`).
The baseline is `product/`: `briefing/market_card.py` raises "not built yet".

## What is protected (the builder never sees it)
`acceptance/a6_market_watchlist.py` and its child runner `acceptance/a6_child.py`, pinned by SHA-256 in the task and
written before any candidate. Each check runs the candidate's `market_card` in a child process, under an operating-system sandbox that denies
network access, against a mocked ECB source. The child prints only the card's data; the suite validates it as a
market_watchlist reference and draws the card itself. Anything but exactly one result line is a REJECT.

| Check | What it demands |
| --- | --- |
| K1 | rows are the traveler's currencies with the source's prices, and no others |
| K2 | the publication day is shown, as a daily reference rate; after a weekend it is the last publication day, never today |
| K3 | the card says "daily reference rate, not a live quote" and never calls a rate live or real time |
| K4 | the day-on-day change is computed from the two reference days, named, with the right numbers; with one reference day it says the change is unavailable, never zero |
| K5 | a failed source gives an unavailable card with a reason and no rate, new or old |
| K6 | a garbage, zero or partial source answer is unavailable, never a zero or a made-up row |
| K7 | the card says "Currencies only; market hours not provided" |
| L1 | exactly one provenance label and exactly one freshness line; no REPLAY, no DELAYED |
| M1 | the payload never says live, and never says delayed for a daily rate |
| N1 | the candidate has no network of its own: the sandbox must stop a connection (this needs `sandbox-exec`, which macOS has; on a machine without it the check fails and is never skipped) |

## Candidates, each judged by the gate
| Candidate | Decision | Named gate |
| --- | --- | --- |
| `market-good` | ACCEPT | all ten checks |
| `market-shows-live` | REJECT | K2, K3, L1, M1: the daily rate shown as a live quote |
| `market-invents-on-failure` | REJECT | K5, K6: typical rates shown when the ECB fails |
| `market-edits-suite` | REJECT | protected file edited, before any suite runs |

N1 needs a machine with `sandbox-exec`. The factory runs on the facilitator's Mac; if a class laptop lacks it, run the gate on the facilitator's Mac and say so.

`run_a6.py` is a local stand-in for the factory's gate. Exit 0 ACCEPT, 1 REJECT, 2 could not run.
The child process and the sandbox keep candidate code out of the process that decides, and with no network it cannot
reach anything else. A candidate that prints extra lines is refused. A forger who rebuilt a valid card for every scenario
would still pass, so the protected suite and the pins are a gate, not a proof. Say so in class.

Numbering: K1 and K6 here are the plan's K3, K3 with L1 and M1 are the plan's K1 and M2, and N1 is the plan's K5.
