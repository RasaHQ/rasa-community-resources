# Facilitator script: agentic software factories on Rasa Mantle

Thursday 22 October 2026, 14:30 to 17:30 London time (13:30 to 16:30 UTC), in person, three hours. You are the facilitator and this is your script. The one-page version for the table is `FACILITATOR-CARD.md`.

Status: DRAFT 2026-10-18. The author ran every command below, in order, on a Mac, through `factory/rehearse.py` (27 of 27 steps matched, each on both its output and its exit status, 80 to 100 seconds in all; `--self-check` shows a wrong exit status or wrong output fails a step), with the pinned environment (`rasa-pro` 3.21.0.dev5), and the outputs match what the script says. That run was the author's, not yours: rehearse it on your own machine ("Before the day"). The author did not run the profrod.ai lessons in the room's setting, did not run a live model and did not test the pre-synced copy on a second machine.

The room is unknown: 5 to 40 people, so everything is done in pairs or small groups of up to four. With 5 people it is one table; with 40 it is ten tables, and you work the room, not the screen.

## What the room leaves with

1. A factory they ran: a task, an isolated change, a protected check, a decision (`factory/factory.py`). The method is profrod.ai Lessons 1 and 2.
2. One failure no test of their own would catch: a Mantle confirmation gate that compiles away with no engine finding (`factory/show_gate.py`).
3. A vendor agent's answer is advice, and the write that follows still waits for a person: its answer is advice, and the write that follows still waits for a person (`openai-mcp/`). The vendor in the room is a stub.
4. A coding agent's work, read and judged, from the 18 recorded runs.
5. A number with an interval, and a sentence about what it does not support (`factory/measure.py`).

## What this session does not show

No live model call, no OpenAI call and no Mantle conversation is part of the plan. Every check reads what the engine compiles from project files. If a live run is done in the room, say so and say that it is one run. Say this out loud in the first ten minutes: "Nothing today runs against a live model. The vendor agent is a stub."

## Before the day

Do these on the machine and network you will use, at least a day before.

- [ ] Clone this repository and note the commit. Participants use that commit. There is no zip.
- [ ] From `workshops/software-factories-masterclass/factory/`: `uv sync --frozen`, then `uv run python factory.py tasks/a1-block-card.json candidates/block-card-good runs/check`. Expect ACCEPT. (The author's four-factory-run block took 82 seconds including the first import.)
- [ ] `uv sync` downloads about 750 MB. Do not do it in class. Bring a pre-synced copy of the cloned folder, including `factory/.venv`, on two USB drives. A venv is tied to the operating system and Python of the machine that made it: test the copy on a spare laptop of each kind that will be in the room, and where it fails, have those people sync at home or pair up.
- [ ] Rehearse: from `factory/`, `uv run python rehearse.py`. It runs the commands of every block in session order, offline (the two opening blocks as `OFFLINE-OPENING.md` teaches them, not the profrod.ai lessons), and prints the time and result of each block. A step passes only if its output and its exit status both match. `uv run python rehearse.py --self-check` proves that rule on stub commands. It exits 0 only if all 27 steps match. Run it on the machine you will present from, and keep the printout.
- [ ] Read `PREWORK.md`, the draft of the message participants get beforehand. It is yours to send or change.
- [ ] Print `FACILITATOR-CARD.md`, one copy for you and one for each table.
- [ ] Decide the fallback in advance (see "If something fails").

## Room checklist

| Item | Check |
| --- | --- |
| Laptops | Every pair has at least one laptop with the pre-synced folder and a terminal. People without one pair up. |
| Python and uv | `uv --version` works; Python 3.11 or newer. |
| wifi | No block needs it once the repository is cloned and synced: the two opening blocks have an offline version (`OFFLINE-OPENING.md`). Test it anyway, then do not depend on it. |
| Projector | Terminal font large enough for the back row. |
| Power | Strips for the number of laptops. |
| Spare laptop | One, pre-synced, to take over a pair whose machine fails. |
| USB drives | Two, with the pre-synced folder. |
| Printouts | The card for you and for each table. |
| Shared place for results | A folder or drive where pairs copy their `factory/runs/` folders at 17:10. |
| Clock | A visible clock; the blocks below are time-boxed. |

## Run of show

All times London. "Say" is what you say, in your words; "Show" is what is on the screen; "Do" is what participants do. Commands run from `workshops/software-factories-masterclass/factory/` unless a block says otherwise; write `uv run` in front of `python` if you did not activate the environment.

| Clock | Min | Block |
| --- | --- | --- |
| 14:30 | 10 | A grader the builder cannot edit is the only review a dark factory has |
| 14:40 | 20 | A forged pass fools the first factory and is rejected by the second |
| 15:00 | 30 | The engine reports nothing when a confirmation gate has silently disappeared |
| 15:30 | 10 | Break |
| 15:40 | 30 | A vendor agent's answer is advice, and the write that follows still waits for a person |
| 16:10 | 30 | A coding agent's summary is a claim until you have read its diff |
| 16:40 | 10 | Break |
| 16:50 | 20 | Two changes that pass alone can fail together, and the builder cannot approve its own release |
| 17:10 | 15 | A few runs support a count with an error bar, not a pass rate |
| 17:25 | 5 | The grader is not the builder's, the engine can be silent, and advice is not permission |

### 14:30 A grader the builder cannot edit is the only review a dark factory has (10 min)

- Say: In a dark factory the evaluation is the only review. If the builder can edit the check, the check proves nothing. A pass rate is a count with an error bar. Nothing today runs against a live model; the vendor agent is a stub.
- Show: profrod.ai, course "Towards Dark Software Factories", Lesson 1, if the room is online. Offline: `OFFLINE-OPENING.md`, 14:30 section, which needs no network.
- Do: Answer the one question in the offline page, or the lesson's checkpoint, with your partner.

### 14:40 A forged pass fools the first factory and is rejected by the second (20 min)

- Say: A defect the agent's own tests missed is the whole course in one run.
- Show: profrod.ai Lesson 2 and its three commands, if the room is online. Offline: the four commands in `OFFLINE-OPENING.md`, 14:40 section, from this repository.
- Do: Pairs run the commands; they print ACCEPT, REJECT, ACCEPT (the first factory is fooled), REJECT.
- If a pair is stuck: the lesson's NOT_READY message names the cause, almost always Python or the environment. Read it aloud.

### 15:00 The engine reports nothing when a confirmation gate has silently disappeared (30 min)

- Say: The engine reported nothing and the gate was gone. Who owns that requirement?
- Show and Do, in this order:

      python factory.py tasks/a1-block-card.json candidates/block-card-good runs/good                 # ACCEPT
      python factory.py tasks/a1-block-card.json candidates/block-card-gate-omitted runs/omitted     # REJECT
      python factory.py tasks/a1-block-card.json candidates/block-card-gate-false runs/false         # REJECT
      python factory.py tasks/a1-block-card.json candidates/block-card-gate-deleted runs/deleted     # REJECT
      python show_gate.py candidates/block-card-gate-omitted

  The last command prints `engine findings: 0` and `block_card gate: OFF (compiled to None)`.
- Land it: the engine said nothing and the gate is off. The builder's own tests pass on all three; only the protected suite catches them. Ask each pair for one sentence: what did the engine say, and what did the gate do?

### 15:30 Break (10 min)

Walk the room. Fix any machine that did not run the previous block now.

### 15:40 A vendor agent's answer is advice, and the write that follows still waits for a person (30 min)

- Say: You cannot put a vendor's agent under your acceptance suite. You can put the line between its answer and your system's next action under it. The vendor's answer is advice; the write that follows still waits for a person.
- Show: `openai-mcp/project/skills/review_dispute/skill.md` and `openai-mcp/server/reviewer_server.py`. Say again that the server is a stub and that the OpenAI path has not run.
- Do, from `openai-mcp/`, with the pack's environment (`../factory/.venv/bin/python`) and `PYTHONPATH` set to the `factory/` folder:
  1. Write down which of the seven edits the suite will reject, and why.
  2. `python -I experiments.py project`, then `MANTLE_PROJECT=$PWD/project python grade_variants.py project`.
  3. Compare with your list. Where did the engine say nothing, and where did the suite?
- Land it: six edits are REJECTED. The seventh, the confirmation question replaced by "Done.", is ACCEPTED, although the control is weakened. The suite was written after these edits were known, so it catches them and no others. Ask each pair: what check would reject it?
- Stretch: write that check into a copy of `acceptance/a4_review_dispute.py` and rerun; then find a different edit it also accepts. There always is one.
- The author's run of both commands took 23 seconds.

### 16:10 A coding agent's summary is a claim until you have read its diff (30 min)

- Say: Read the diff before you read the summary.
- Show: one recorded run, for example `agent-runs/claude-code-2026-10-15/claude-a1-block-card-1/`: the final message, the patch, the decision.
- Do: Each pair reads a different recorded run (there are nine per agent, under `agent-runs/claude-code-2026-10-15/` and `agent-runs/codex-2026-10-15/`) and compares what the agent said with what the diff changed.
- Say: all 18 recorded runs were accepted. Do not promise the room a failure.
- Optional, only if a live run is available and you decide to: one run of a coding agent on task A1 in front of the room, once. It is one run and says nothing about a rate. The plan does not need it.

### 16:40 Break (10 min)

### 16:50 Two changes that pass alone can fail together, and the builder cannot approve its own release (20 min)

- Say: Passing alone says nothing about the trunk. And the builder cannot approve its own work.
- Do, integration (each candidate is judged first, then merged):

      python factory.py tasks/a2-rule-digits.json candidates/rule-digits-good runs/digits-01
      python factory.py tasks/a3-rule-confirm.json candidates/rule-confirm-on-baseline runs/confirm-alone
      python factory.py tasks/a3-rule-confirm.json candidates/rule-confirm-on-digits runs/confirm-rebased
      python integrate.py trunk integration/m1-digits.json                  # MERGED
      python integrate.py trunk integration/m2-confirm-on-baseline.json     # REFUSED - STALE_BASE
      python integrate.py trunk integration/m3-confirm-on-digits.json       # MERGED

  The second candidate passes alone and is refused because it was built on a trunk that has moved.
- Do, release:

      python approve.py allow releases reviewer
      python approve.py sign candidates/block-card-good codex approvals/by-codex.json
      python release.py publish runs/good/decision.json candidates/block-card-good approvals/by-codex.json releases     # REFUSED
      python approve.py sign candidates/block-card-good reviewer approvals/by-reviewer.json
      python release.py publish runs/good/decision.json candidates/block-card-good approvals/by-reviewer.json releases  # published
      python release.py verify releases                                                                                 # SERVING

  This needs `runs/good` from the 15:00 block and an `approvals/` folder (`mkdir approvals`). The first publish is refused because `codex` is not on the approvers list.
- The author's run of this block took 18 seconds for the integration part.

### 17:10 A few runs support a count with an error bar, not a pass rate (15 min)

- Do: Each pair copies its `factory/runs/` folders to the shared place. Then you run:

      python measure.py report agent-runs/claude-code-2026-10-15 agent-runs/codex-2026-10-15
      python measure.py needed 0.9
      python policy.py what-if policy.json 35 35

  The report prints `18 runs, rasa-pro 3.21.0.dev5`, `accepted: 18 of 18 = 1.00` and a Wilson 95% interval of 0.82 to 1.00. `needed 0.9` prints 35 runs with none failing. `what-if 35 35` prints ELIGIBLE for promotion to L1, which is arithmetic only, with no data behind it.
- Say: What do these runs support? What would we need to claim more? A blank field stays blank.
- If the room's pooled runs are in the shared folder, run `measure.py report` over those folders too, and say how many runs there are and that they are this room's.

### 17:25 The grader is not the builder's, the engine can be silent, and advice is not permission (5 min)

- Say: Three things to take: the grader is not the builder's to edit; the engine can be silent where the gate is gone; the vendor's answer is advice. And what we did not do: we did not run a live model.
- Hand out: the repository link and the commit.

## If something fails

| What happens | What you do |
| --- | --- |
| A laptop will not sync or run | Pair that person with a neighbour, or hand them the spare laptop. |
| A pair gets NOT_READY | Read the reason aloud; it is almost always Python or `uv sync`. |
| Everything is slow | Skip the stretch tasks, not the "Land it" lines. |
| The projector or your laptop fails | Use the printed card and the recorded runs under `agent-runs/`; read one decision aloud. |
| wifi is down | No block depends on it. |
| An agent edited files it should not have | `collect.py` reports it and the factory refuses it. A teaching moment. |
| A run passes everything | Good. Say so. Do not coach the room toward failures. |

## What not to claim afterwards

- Not "Mantle agents are safe" or "unsafe". The checks read compiled configuration. Nothing here tests an agent in conversation with a live model.
- Not "coding agents are X percent reliable". The pool is two agents on three tasks, on one pre-release engine build (3.21.0.dev5).
- If the room does not reach 35 clean runs, do not claim a 90 percent lower bound. `measure.py needed 0.9` says how many runs that takes.
- Nothing about the vendor agent's real behaviour: the vendor in the room is a stub.

## After the session

- [ ] Publish the pooled `report` output exactly as printed, with the date and the engine build.
- [ ] File the run folders. Keep failed runs.
