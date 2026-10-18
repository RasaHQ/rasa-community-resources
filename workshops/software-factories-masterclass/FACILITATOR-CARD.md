# Facilitator card: Thu 22 Oct 2026, 14:30 to 17:30 London (13:30 UTC)

In person, 5 to 40 people, pairs or groups of up to four. Offline by default: nothing runs against a live model unless you choose the one optional live coding-agent run (then say so, and that it is one run); the vendor agent is a stub. Say the matching line in the first ten minutes and at 17:25. Full script: `FACILITATOR.md`. `OFFLINE-OPENING.md` is the 14:30 and 14:40 material, online or not. Rehearse: `uv run python rehearse.py` in `factory/`.

| Clock | Block | One line to say | Pairs do |
| --- | --- | --- | --- |
| 14:30 | A grader the builder cannot edit is the only review a dark factory has | In a dark factory the evaluation is the only review | Answer the question in `OFFLINE-OPENING.md` |
| 14:40 | A forged pass fools the first factory and is rejected by the second | A defect the agent's own tests missed is the whole course | Offline toy loop: ACCEPT, REJECT, ACCEPT (first factory fooled), REJECT (second factory) |
| 15:00 | The engine reports nothing when a confirmation gate has silently disappeared | The engine reported nothing and the gate was gone | `factory.py` on good + 3 silent-gate candidates; `show_gate.py` |
| 15:30 | Break | | |
| 15:40 | A vendor agent's answer is advice, and the write that follows still waits for a person | You can grade the line after the vendor's answer, not the vendor | From `openai-mcp/`: `../factory/.venv/bin/python -I experiments.py project`, then `.../python grade_variants.py project`; predict, then compare |
| 16:10 | A coding agent's summary is a claim until you have read its diff | Read the diff before you read the summary | Read a recorded run; all 18 were accepted |
| 16:40 | Break | | |
| 16:50 | Two changes that pass alone can fail together, and the builder cannot approve its own release | Passing alone says nothing about the trunk | `integrate.py` (STALE_BASE refusal); `release.py` (builder refused) |
| 17:10 | A few runs support a count with an error bar, not a pass rate | What do these runs support? | `measure.py report` over the 18 recorded runs, `needed 0.9`, `policy.py what-if`; the scripted candidates are examples, not results |
| 17:25 | You leave knowing who may edit the check, where the engine is silent and why advice is not permission | The grader is not the builder's; the engine can be silent; advice is not permission | Nothing |

Landing lines: all three silent-gate candidates pass the builder's tests and are REJECTED by the protected suite. In the vendor block six edits are rejected and one ("Done." replacing the question) is ACCEPTED: a known gap. The recorded report is 18 of 18 accepted, Wilson 95% 0.82 to 1.00; 35 clean runs are needed for a 0.9 lower bound.

If it fails: practised before? move `runs`, `trunk`, `releases`, `approvals` aside (`FACILITATOR.md`, Reset); pair people up; spare laptop; NOT_READY means read the reason aloud (Python or `uv sync`); no block needs wifi; projector down means the printed card and one recorded decision read aloud.

Do not claim: that Mantle agents are safe or unsafe; any pass rate for coding agents; anything about the real vendor agent.
