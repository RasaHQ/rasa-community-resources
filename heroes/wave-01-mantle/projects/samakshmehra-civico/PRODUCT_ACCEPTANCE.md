# Civico product acceptance

The goal is a caller who feels understood, with a correct saved report. More
features are not the milestone. All assignments and targets are demo data.

## Two-minute showcase

Use a fresh temporary register to avoid rehearsals becoming duplicate incidents.
Speak naturally and answer the question actually asked; do not rush the next line.

Normal report:

1. “Garbage bags have been outside the Juniper School gate in Indirapuram for three days.”
2. If asked for a number: “Nine zero zero zero zero zero zero zero zero one.”
3. Check the summary, then “Yes, submit it.”
4. “Can you check that report?”

Recovery case, in a fresh conversation:

1. “The street light at Juniper Heights main gate in Vasundhara is not working.
   My callback number is nine zero zero zero zero zero zero zero zero five.”
2. At the summary: “Actually, the other gate.”
3. If asked which gate, supply a real detail for this fictional incident, such
   as “the back gate”. Check that the building and locality are retained.
4. Approve only after hearing the corrected summary.

## Acceptance checks

| Check | Evidence required |
|---|---|
| Details accepted in any order | Give locality before issue; no loss of either |
| Locality/PIN separate from incident spot | PIN-only intake still asks for landmark |
| No mandatory repeat description | “The streetlight is not working” is used directly |
| A correction retains relevant context | Named building/locality survive “the other gate” |
| Only one submission approval | No write before consent; fresh consent after changes |
| Useful receipt | Saved reference, demo assignment, target, how to track |
| Honest cancellation/failure | No saved row and no claimed submission |
| No duplicate question in one turn | Inspect bot events and listen to the audio |
| Voice and text agree | Manual microphone test; text-only tests do not prove this |

## Measure a completed conversation

The Inspector sender/conversation ID or the ID printed by `demo_call.py` can be
used to inspect a tracker without writing anything:

```bash
make quality ARGS='--sender YOUR_CONVERSATION_ID --server http://localhost:5007'
```

Or analyse an exported tracker offline:

```bash
.venv/bin/python scripts/conversation_quality.py --tracker exported-tracker.json
```

The output includes successful saved-report count, post-review correction calls,
saves after corrections, duplicate questions in one turn, repeat-question review
candidates, empty text turns, internal tool text, and time to first bot text.
It deliberately excludes caller messages, numbers and references. Do not publish
the raw tracker: it can contain caller information.

Review candidates are not verdicts. Asking again after unclear speech can be
correct. A successful write after a correction is not proof that the correct
landmark was saved: inspect SQLite or track the report. A snapshot of an active
turn can look empty. Text-event timing is not audio latency.

For beta feedback, record the scenario, model filename, observed behavior and
scorecard. Keep microphone interruption, repeated audio, and audio/text ordering
as separate manual checks. Do not describe them as fixed from an offline pass.
