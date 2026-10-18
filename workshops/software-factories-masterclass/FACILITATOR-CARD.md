# Facilitator card: Thu 22 Oct 2026, 14:30 to 17:30 London (13:30 UTC)

In person, 5 to 40 people, pairs or groups of up to four. Offline: nothing runs against a live model; the vendor agent is a stub. Say so in the first ten minutes. Full script: `FACILITATOR.md`. No wifi: `OFFLINE-OPENING.md` replaces the two profrod.ai blocks. Rehearse: `uv run python rehearse.py` in `factory/`.

| Clock | Block | One line to say | Pairs do |
| --- | --- | --- | --- |
| 14:30 | Why a grader the builder cannot edit | The evaluation is the only review in a dark factory | Answer the Lesson 1 checkpoint |
| 14:40 | A forged pass fools the first factory and is rejected by the second | A defect the agent's own tests missed is the whole course | Lesson 2: ACCEPT, REJECT, REJECT |
| 15:00 | Mantle as product, engine as grader | The engine reported nothing and the gate was gone | `factory.py` on good + 3 silent-gate candidates; `show_gate.py` |
| 15:30 | Break | | |
| 15:40 | Vendor agent behind a tool boundary | The vendor's answer is advice; the write waits for a person | `openai-mcp/`: `experiments.py`, `grade_variants.py`; predict, then compare |
| 16:10 | A coding agent's summary is a claim until you have read its diff | Read the diff before you read the summary | Read a recorded run; all 18 were accepted |
| 16:40 | Break | | |
| 16:50 | Two teams, one file; release | Passing alone says nothing about the trunk | `integrate.py` (STALE_BASE refusal); `release.py` (builder refused) |
| 17:10 | A few runs support a count with an error bar, not a pass rate | What do these runs support? | `measure.py report`, `needed 0.9`, `policy.py what-if` |
| 17:25 | The grader is not the builder's, the engine can be silent, and advice is not permission | The grader is not the builder's; the engine can be silent; advice is not permission | Copy `runs/` to the shared place |

Landing lines: all three silent-gate candidates pass the builder's tests and are REJECTED by the protected suite. In the vendor block six edits are rejected and one ("Done." replacing the question) is ACCEPTED: a known gap. The recorded report is 18 of 18 accepted, Wilson 95% 0.82 to 1.00; 35 clean runs are needed for a 0.9 lower bound.

If it fails: pair people up; spare laptop; NOT_READY means read the reason aloud (Python or `uv sync`); no block needs wifi; projector down means the printed card and one recorded decision read aloud.

Do not claim: that Mantle agents are safe or unsafe; any pass rate for coding agents; anything about the real vendor agent.
