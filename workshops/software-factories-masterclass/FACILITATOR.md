# Facilitator runbook: agentic software factories on Rasa Mantle (3 hours, in person)

DRAFT 2026-10-15. It accompanies this pack; the technology-neutral course is Towards Dark Software Factories on profrod.ai.
Lines marked TO CONFIRM need an answer from the operator. Nothing marked TO CONFIRM has been run.

Open session details, to fill in when known: date [DATE], room [ROOM], headcount [HEADCOUNT], level [LEVEL].
Rasa supplies API keys and Mantle licences for everyone. The track was built and tested offline with no licence, so any step that needs a live Mantle model call is unverified.

## What the room leaves with

1. A factory they ran: task, isolated change, protected check, decision (Lessons 1, 2, 10).
2. One concrete failure no test of their own would have caught: a Mantle confirmation gate that compiles away with zero engine findings (Lesson 10).
3. A real coding agent's work, collected and judged (Lesson 11), by Claude Code or Codex, their choice, or both. The course already holds 18 recorded runs (9 per agent), all accepted; do not promise the room a failure.
4. Their own runs pooled into one report with an interval, and a sentence about what the numbers do not support (Lesson 14).

## Before class (facilitator, the day before)

- [ ] Download `mantle-factory.zip` and `factory-course-full.zip` from the course page; check the zip hashes against the PR.
- [ ] On the room's wifi and a spare laptop: unzip, `uv sync`, `uv run python factory.py tasks/a1-block-card.json candidates/block-card-good runs/check`. Expect ACCEPT in about five seconds after the first import.
- [ ] `uv sync` downloads about 750 MB. Do NOT make participants do it in class. Either they sync at home, or you bring a pre-synced copy (TO CONFIRM: how: USB drive, shared folder, or the uv cache).
- [ ] Keys and licenses (TO CONFIRM): Rasa provides API keys and Mantle licences for everyone. Which provider for the Mantle model group; which for Claude Code (login or ANTHROPIC_API_KEY); which for Codex (login or OPENAI_API_KEY); how they reach participants; spending limits.
- [ ] Both agents installed and signed in on every laptop: `claude --version`, `codex --version`. Verified end to end on 2026-10-15 with Claude Code 2.1.299 and codex-cli 0.162.1 (18 recorded runs in the course). Newer versions may differ.
- [ ] Codex needs `--skip-git-repo-check` in a folder that is not a git repository (the lesson's command has it). Claude Code run headless (`claude -p`) must not be launched from inside another Claude Code session: it hangs. Participants running it in an ordinary terminal are fine.
- [ ] Agent timing from the recorded runs, to plan blocks: the card skill (A1) took 78 to 222 seconds per run, the one-rule tasks (A2, A3) 8 to 17 seconds.
- [ ] No Docker anywhere. Nothing in the plan needs it.
- [ ] A shared place for run folders after the experiment (TO CONFIRM: drive, Slack, or USB).

## Agenda

| Clock | Block                                                | Lesson | What participants do                                                                                        | Facilitator says                                                                              |
| ----- | ---------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 0:00  | Why a factory needs a grader the builder cannot edit | 1      | Listen, answer one checkpoint                                                                               | The evaluation is the only review in a dark factory. A pass rate is a count with an error bar |
| 0:15  | The loop, on a toy                                   | 2      | Run the three commands that ACCEPT, REJECT, REJECT                                                          | A defect the agent's own tests missed is the whole course in one run                          |
| 0:35  | Mantle as the product, the engine as the grader      | 10     | `uv run python factory.py ...` on the good candidate and the three silent-gate candidates; `show_gate.py`   | The engine reported nothing and the gate was gone. Who owns that requirement?                 |
| 1:05  | Break                                                |        |                                                                                                             |                                                                                               |
| 1:15  | Brief a coding agent                                 | 11     | `scratch.py`, run Claude Code or Codex on task A1, `collect.py`, `factory.py`                               | Read the diff before you read the summary                                                     |
| 1:50  | Two teams, one agent.yml                             | 12     | Run the nested-rule check, then the integration sequence                                                    | Passing alone says nothing about the trunk                                                    |
| 2:15  | Release and recover (short)                          | 13     | Run the approver refusal and `verify`                                                                       | The builder cannot approve itself                                                             |
| 2:25  | The experiment                                       | 14     | Each participant runs A2 and A3 with their agent (A1 done), adds meta.json, copies runs to the shared place | One attempt per task. A blank field stays blank                                               |
| 2:45  | Pool, report, decide                                 | 14, 9  | Facilitator runs `measure.py report`, `measure.py needed 0.9`, `policy.py what-if` live                     | What do these runs support? What would we need to claim more?                                 |
| 2:55  | Close                                                |        |                                                                                                             |                                                                                               |

## Hard parts

- **The first `uv sync`.** Covered above. If a laptop lacks it, pair that person with a neighbor for the first blocks.
- **An agent that passes everything.** Good. The report says so. Do not coach the room toward failures.
- **An agent that edits files it should not.** `collect.py` reports it, the factory refuses it, and it is a teaching moment, not a rule violation.
- **Agent runs that take longer than the block.** One attempt per task; stop at the time box and record the run as it stands (`meta.json` with what is known).
- **Different agent versions in one pool.** The report prints `rasa-pro` once; the agent and its version live in each `meta.json`. Do not average across versions without saying so.
- **A participant's run fails with NOT_READY.** That is the Lesson 10 outcome. Read the reason aloud; it is almost always Python or `uv sync`.

## What not to claim afterwards

- Not "Mantle agents are safe" or "unsafe". The checks read compiled configuration. Nothing in the track tests an agent in conversation with a live model.
- Not "coding agents are X percent reliable". The pool is this room's agents on three tasks, on one pre-release engine build (3.21.0.dev5).
- If the room does not reach 35 clean runs, do not claim a 90 percent lower bound. `measure.py needed 0.9` says how many runs that takes.

## After class

- [ ] Publish the pooled `report` output and the agent list exactly as printed, with the date and engine build.
- [ ] File the run folders. Keep failed runs.
