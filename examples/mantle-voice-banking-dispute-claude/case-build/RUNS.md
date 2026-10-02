# Held-out vocabulary: does a vocabulary help names it does not list?

Run on 2026-10-02 (UTC 2026-10-01 23:42 to 2026-10-02 00:14) from one
laptop, with the stack in `integrations.yml`: `claude-sonnet-5-5`,
Speechmatics realtime (`enhanced`, EU endpoint) in, Rime `mistv3`
(`ironwood`) out, over `browser_audio`, with the caller WAVs in
`caller-audio/` replayed byte for byte.

## Why

On 2026-09-29 a seven-entry Speechmatics `additional_vocab` (the six ledger
merchants and the customers' surname, `--variant custom-vocab`) took the 11
calls that carry those names from 6 to 11 passing. Every entry came from the
script's own names. These runs test a vocabulary that does not list the
names the calls use.

## The split

The ledger (`lib/fixtures/northgate_disputes.json`) has six merchants. Split
by transaction id, first three and last three:

| Half | Merchants | Role |
|---|---|---|
| First | Brightmart Online (NB-TXN-3101), Lakeview Fuel (3102), Hollins Fitness (3104) | Held out: said in the calls, not in the vocabulary |
| Second | Saffron Table (3105), Metro Cabs (3106), Cinnabar Streaming (3107) | The vocabulary (`--variant held-out-vocab`) |

The split in transaction-id order also puts every merchant name the
2026-09-29 default run misheard ("Bright Mart", "Breitbart", "bright mark",
"lake view", "Haaland's") in the held-out half. A held-out name that the
default already hears correctly could not show a vocabulary helping.

**The surname is in neither half.** No run here lists "Raghunathan", so the
surname is reported on its own row and is a held-out name in both
conditions.

The calls are the 11 whose checked merchant tokens are all in the held-out
half, the same 11 as the 2026-09-29 custom-vocab run.
`correction-other-charge-at-confirmation` names both Cinnabar Streaming and
Brightmart Online, so it is in neither set.

## Commands

From the repository root. `--budget-usd 6.93` is the 3.94 USD the ledger
held before these runs plus the 3.00 USD cap for the experiment.

```bash
B=examples/mantle-voice-banking-dispute-claude
CALLS=normal-brightmart-unrecognised,normal-date-said-numerically,normal-second-customer-arjun,normal-dispute-and-block-card,adversarial-refund-now,adversarial-ambiguous-file-both,adversarial-skip-confirmation,recovery-ambiguous-then-amount,correction-recognises-gym,correction-self-corrected-amount,short-reply-yes
python3 scripts/case_builds/run_build.py $B --budget-usd 6.93 --only $CALLS --variant held-out-vocab --label 2026-10-02-held-out-vocab
python3 scripts/case_builds/run_build.py $B --budget-usd 6.93 --only $CALLS --label 2026-10-02-held-out-control
python3 $B/case-build/held_out_vocab.py
```

The server log of the first run shows the vocabulary sent to Speechmatics
(`"additional_vocab": [{"content": "Saffron Table"}, ...]`); the control's
shows `"additional_vocab": null`. `held_out_vocab.py` writes
`held-out-vocab.json` with every count by call, and puts the two
2026-09-29 runs of the same 11 calls next to them.

## Per call

| Call | 09-29 no vocabulary | 09-29 full vocabulary | 10-02 held-out vocabulary | 10-02 no vocabulary |
|---|---|---|---|---|
| normal-brightmart-unrecognised | pass | pass | pass | pass |
| normal-date-said-numerically | pass | pass | pass | pass |
| normal-second-customer-arjun | fail | pass | pass | pass |
| normal-dispute-and-block-card | pass | pass | pass | pass |
| adversarial-refund-now | fail | pass | fail | fail |
| adversarial-ambiguous-file-both | pass | pass | pass | pass |
| adversarial-skip-confirmation | pass | pass | fail | fail |
| recovery-ambiguous-then-amount | fail | pass | fail | fail |
| correction-recognises-gym | fail | pass | fail | fail |
| correction-self-corrected-amount | fail | pass | fail | fail |
| short-reply-yes | pass | pass | pass | pass |
| **Passed** | **6/11** | **11/11** | **6/11** | **6/11** |

No call flipped between the held-out vocabulary and the same-day control.

## Checked tokens by kind

As written / after spoken numbers become digits / checked, over the 11
calls:

| Kind | 09-29 no vocabulary | 09-29 full vocabulary | 10-02 held-out vocabulary | 10-02 no vocabulary |
|---|---|---|---|---|
| Held-out merchant | 1 / 1 / 11 | 11 / 11 / 11 | 1 / 1 / 11 | 1 / 1 / 11 |
| Surname | 10 / 10 / 11 | 11 / 11 / 11 | 10 / 10 / 11 | 10 / 10 / 11 |
| First name | 11 / 11 / 11 | 11 / 11 / 11 | 11 / 11 / 11 | 11 / 11 / 11 |
| Date | 11 / 25 / 28 | 12 / 26 / 28 | 11 / 24 / 28 | 11 / 24 / 28 |
| Amount | 0 / 10 / 10 | 0 / 10 / 10 | 0 / 9 / 10 | 0 / 9 / 10 |
| Card ending | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 2 / 2 |

With the held-out vocabulary the merchant names were heard as in the
control, call by call:

- Brightmart: "Bright Mart online" (4 calls), "Breitbart Online" (2), "bright
  mark" (1)
- Lakeview: "lake view fuel" (2); "Lakeview fuel" once, in
  `recovery-ambiguous-then-amount`
- Hollins: "Holland's fitness", then "Haaland's fitness"
- Surname: "Priya Ragunathan" in `recovery-ambiguous-then-amount`, where
  verification then failed (`identity_mismatch`), in both conditions

In `adversarial-skip-confirmation` both 10-02 runs split the first caller turn
after "I don't." and heard the rest as the next turn: "Size a charge of
₹2,499 from Breitbart Online on the 22nd of September. ..." (held-out
vocabulary) and "Denies a charge of ₹2,499 from Breitbart Online . On the 22nd
of September. ..." (control). That moves one date and one amount out of the
checked turn and accounts for the lower date and amount counts. The call
then failed on "Breitbart", as `adversarial-refund-now` did.

`normal-second-customer-arjun` passed in both 10-02 runs. It failed on
2026-09-29 when Speechmatics heard "Breitbart Online"; on 10-02 it heard
"Bright Mart online" in both runs, which the merchant match accepts because
it ignores word boundaries.

## False positives

A false positive is a vocabulary entry, or one word of a multi-word entry,
in what Speechmatics produced for a turn whose script does not contain it.
"Saffron", "Metro", "Cinnabar", "Table", "Cabs" and "Streaming" appear in no
transcript of the held-out run: 0. The 2026-09-29 full-vocabulary run,
checked the same way over the same 11 calls, also has 0.

## What this shows

On these 11 calls, a vocabulary of three other merchants from the same
ledger changed no outcome and no checked token. The 2026-09-29 gain came
from listing the names the callers said. One run per condition, one day,
synthetic callers.

Spend: 2.17 USD (held-out vocabulary 1.09, control 1.08; ledger 3.94 before,
6.10 after).
