# Explain what you built

Use these prompts at your own pace. Answer before reading the notes. You do not need a facilitator to decide whether to move on.

| Checkpoint | Show | Explain |
|---|---|---|
| Travel demo | Four labeled cards and a changed transfer allowance | Which values are observations, estimates, forecasts and assumptions? |
| First builder run | ACCEPT at limit 2, followed by NOT DONE | Why can the product gate pass while the learner completion check fails? |
| Your change | A fresh limit-1-or-3 attempt and ch05 OK | Which files were checked, and what would invalidate the result? |
| Rejection | A daily-rate card falsely labeled live, and its REJECT | Which requirement failed? Why should you keep this example? |
| Integration | A standalone card and a refused repeated integration | What does changing the base invalidate? |
| Recovery track | A bounded retry and a duplicate request doing no extra work | What is the difference between retrying a failed attempt and repeating an accepted job? |

## Notes to compare with your answer

- The flight position is an observation at a time. Arrival is a computed estimate. Weather is a forecast. Transfer is your planning assumption. Currency is a daily reference rate. None is an airline delay guarantee.
- ACCEPT asks whether the candidate meets its task. The chapter completion check also asks whether you made the required learner change. The supplied limit 2 is intentionally not enough for ch05 OK.
- Changing the task, candidate, protected tests or relevant base can invalidate earlier evidence. Keep those versions with the decision.
- A rejected “live rates” label demonstrates a concrete failure. It does not measure how often a model fails in the real world.
- Chapter 7 produces a standalone card. It does not install or restart the travel agent. The complete voice factory still needs its build-job and release connection.
- A provider outage or missing dependency can prevent judgment: NOT_READY. A judged requirement failure is REJECT. A duplicate request should reuse its recorded outcome rather than repeat side effects.

## Your two-minute handoff

Show the request, one failure, the exact accepted output and one remaining limitation. State SCRIPTED, REPLAY or LIVE for each part. If you did not test speech input and output, say “voice unverified.”

A useful final question: what evidence would another group need to trust your release without reading every changed line?
