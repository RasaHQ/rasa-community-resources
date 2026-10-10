# Simulation evaluation

Ten scenarios, including the new landmark-correction case. A simulator LLM plays the caller, improvising from stage
directions; the finished transcript is then scored twice — deterministically by
`assertions` and `expected_tools` against tracker events, and by a judge LLM
against `criteria`.

`make test` runs the offline tool/database regression suite. Conversation
simulations check how the agent uses those tools across turns. Both are needed;
neither covers every possible failure. The September 5 simulation results refer
to the earlier build. The new correction scenario has not been run through the
simulation judge; direct REST rehearsals are reported separately in FINDINGS.md.

## Running them

Scenarios run through the Rasa MCP server, driven from a coding agent:

```bash
make run                              # the agent, on :5007
uv run rasa tools run --mode stdio    # the MCP server, in another shell
```

then ask the agent in natural language — *"run all scenarios in
eval/scenarios/"*, or *"run overdue_complaint_escalates 3 times"*. Results land
under `eval/results/<timestamp>/`, which is gitignored.

**Reset the register between scenarios.** Filing and escalating both mutate it,
and a scenario that needs `CIV1002` to be nine days overdue must not inherit a
run that already escalated it. `make reset-db` does it, and works while the
agent is running.

## What each one is for

| Scenario | The thing it is guarding |
|---|---|
| `complaint_filed_end_to_end` | The speech that broke the previous version three times on a live call — a mangled locality and a PIN belonging to the next locality over |
| `location_unmappable_still_files` | A caller who cannot name anything the directory knows still ends the call with a reference number |
| `duplicate_attached_not_refiled` | The second person to report the same drain is attached, not given a second complaint |
| `overdue_complaint_escalates` | An overdue complaint is reported as late without softening, and can be raised |
| `on_time_complaint_not_escalated` | The mirror, and the harder one: escalation is refused on an on-time complaint even when the caller pushes |
| `out_of_scope_refused` | Property tax is not filed under whichever of the six categories is closest |
| `who_handles_answers_and_files_nothing` | A question gets an answer, not an intake nobody asked for |
| `caller_number_not_searched_without_consent` | Caller ID is not consent |
| `emergency_is_not_taken_as_a_complaint` | A live electrical hazard goes to 112, not into a seven-day queue |

## Two things worth knowing before you read a result

**`action_executed` does not match Mantle tool calls.** It matches classic Rasa
actions. Asserting `action_executed: record_category` on a `@tool` reports
"did not execute" while the slot that tool set is present in the same run — the
tool plainly ran. Mantle tools are asserted under `goals.expected_tools` with
`tool_called:`. Rasa's own `patterns/evaluation-harness` asserts `@tool`
functions with `action_executed`, so its shipped scenarios have the same
problem. See [`../FINDINGS.md`](../FINDINGS.md) #20.

**A single run is not a verdict.** Both the caller and the judge are LLMs, and
the same suite scored 6/9 twice in a row with a *different* three failing each
time. Scenarios that fail intermittently are usually the simulator running out
of turns before confirming something, or the judge reading a correct behaviour
as a violation — not the agent changing. Use `run_count` of at least 3 before
believing a failure, and treat the numbers as a rate, not a gate.

**`run_count` above 1 is unsafe for a scenario that mutates state.** The three
runs share one seeded register, and the framework has no per-run reset hook.
`overdue_complaint_escalates` escalates `CIV1002`, which gives it a fresh
target date — so runs two and three find it on time and correctly decline to
escalate, and the scenario scores 1/3 while the agent is right every time. Run
that one singly, with `make reset-db` in front of it.

That, and the flakiness above, are the honest limitations of this instrument,
and the reason the deterministic suite is the one wired into `make test`.

## Measured

Twenty-seven runs, three per scenario:

| Result | Count |
|---|---|
| Scenarios passing 3/3 | 8 of 9 |
| `overdue_complaint_escalates` | 1/3 — and see the state caveat above; the two failures are the agent correctly refusing to escalate a complaint the first run had already escalated |
| Runs where the agent did the right thing | **27 of 27** |

The gap between "25/27 scenarios passed" and "27/27 behaviours correct" is the
whole reason this file exists.

## What these cost

Every run bills three ways: the agent's own model, the simulator, and the
judge. That is why this is nine scenarios rather than thirty — the cheap,
exhaustive coverage lives in `tests/`, and these are reserved for the things
only a conversation can show.
