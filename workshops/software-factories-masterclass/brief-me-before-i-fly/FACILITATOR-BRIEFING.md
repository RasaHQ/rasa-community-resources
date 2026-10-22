# Facilitator script: "Brief me before I fly" (DRAFT v1, replaces the frozen agenda as the primary plan)

sow: software-factories-masterclass-SOW-02

Thursday 22 October 2026, 14:30 to 17:30 London (13:30 to 16:30 UTC), in person, three hours. The organizer decides by 10:00 UTC on Thursday 22 October: the live check or the scripted path. Run the frozen plan in `../FACILITATOR.md` at its pinned commit only if neither works, and then say nothing about this one.
Everything marked [PRODUCT] uses the companion example `examples/mantle-flight-briefing-openai-agents`, which is merged. The participant commit and the optional facilitator commit are named in the next section. If the new session isn't selected, use the frozen pack at `95512574`.

## Which commit is which
Participants use the class commit `74adca16483ed8444a2c89121bc63cc4bac52332`. The prework addendum names it. The facilitator's live check uses main `66c5d71eb79961e5af6ad86eafdd7693b7e244bc` and follows section 7 of the project README at that commit. The managed OpenAI Agents leg is NOT_RUN until its worker qualification arrives, as section 7 says. If it is still NOT_RUN on Thursday, say so in class. Participants stay on `74adca16`. Don't tell them to update. The clean-clone checks passed at each commit separately.

## What you say first, and what you never say
Say: this is a Rasa-organized class. Rasa Mantle is the center. A dark software factory is how the Mantle agent is built and extended.
Never say: that Mantle has widgets or renders cards (it documents no such feature); that the replay is a real flight; that the transfer time is traffic; that delayed market data is real time; that a model follows these instructions (no model has been shown to).
Say aloud at the start: If you see SCRIPTED on your screen, nothing live ran. The flight is a constructed classroom replay named DEMO101. Every card says REPLAY. The cards are defined by zeocore's contract and shown as text cards in the conversation. The 90-minute transfer is an assumption.

## Before the day (facilitator laptop)
- Environment as in the companion README: two shells, the same runtime-only `BRIEFING_MCP_TOKEN` (at least 32 characters, never written to a file), the worker interpreter and the project interpreter, both built from the resource-owned locks with the verified dev17 wheel (sha256 724fab71d1472aaf8968c2eea7f63f6a9698850ca169d4c84a6484f0ef6e8f40).
- Shell 1, from the example folder: `worker/.venv/bin/python -m briefing`. Shell 2, from `project/`: `.venv/bin/rasa train` then `.venv/bin/rasa inspect`.
- Keys (decision of 2026-10-21): participants run the product on keys handed out IN CLASS, read only from the environment: `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`. Participants bring none. No contributor holds, requests or sees a key; the organizer hands them out by his own method and revokes them after the class. Never type a key into a file, a chat, an email or a screenshot. The doctor command (`class_doctor.py` in the example folder, run with the project interpreter) prints SET or MISSING for each key, never the value, and says which path will run: live OpenAI, live Anthropic or SCRIPTED. The scripted replay (`scripted_demo.py`, same folder and interpreter) always works and is labeled SCRIPTED on screen. Say which path is shown, every time.
- Participants' prework: the earlier one (c894ff24) PLUS the addendum `PREWORK-ADDENDUM-FINAL-74adca16-v2.md` (the class commit, two environments, `class_doctor.py --scripted`, `scripted_demo.py`), which the organizer sends only if the new session is selected. Participants then already hold `74adca16483ed8444a2c89121bc63cc4bac52332` and the two environments. If someone did not run it: they pair with someone who did. Check before the day that the factory lock did not change: `git diff e2a286a8e496aeee0ad2a695031165361693ea8a 74adca16483ed8444a2c89121bc63cc4bac52332 -- workshops/software-factories-masterclass/factory/uv.lock` prints nothing.

## Schedule (UTC / London)
| UTC | London | Min | Block |
|---|---|---|---|
| 13:30 | 14:30 | 15 | The whole thing, end to end, in Mantle |
| 13:45 | 14:45 | 20 | The spec and the scenarios come first |
| 14:05 | 15:05 | 30 | What Mantle compiles can be graded offline |
| 14:35 | 15:35 | 10 | Break |
| 14:45 | 15:45 | 30 | A specialist behind one tool is advice, and its numbers are checked |
| 15:15 | 16:15 | 25 | The honesty rules are acceptance scenarios |
| 15:40 | 16:40 | 10 | Break |
| 15:50 | 16:50 | 30 | The second act: the next feature, specified before it's built |
| 16:20 | 17:20 | 10 | What this does not show |

### 13:30 The whole thing, end to end (15 min) [PRODUCT]
- Do: with both shells running, ask in `rasa inspect`: "Show the constructed Replay DEMO101." Expect flight, weather and arrival-timeline text cards, REPLAY labels, a 90-minute assumed transfer and a 120-minute margin. Then "Replay DEMO101 morning weather": flight and timeline keep their provenance. Then "Replay DEMO101 later arrival": the margin changes to 30 and the old 120 is gone.
- If voice is shown, say which route it is (browser speech or Mantle's own pipeline) and that it adds nothing to the evidence.
- Land it: one conversation, one tool, cards that come from checked data. The rest of the day takes it apart.

### 13:45 The spec and the scenarios come first (20 min)
- Hand out the keys here, one per participant, and run through it together: each types `read -s OPENAI_API_KEY && export OPENAI_API_KEY` (or the same with ANTHROPIC_API_KEY) in their own terminal and pastes the key at the silent prompt, so it never shows on screen or in shell history. Then they run the doctor command. Expect SET for that key and the matching live path. Anyone without a key, or whose doctor says MISSING, stays on SCRIPTED. Do not look at anyone's screen when they type a key, and do not read one aloud.
- Show `SPEC-brief-me-before-i-fly-v5.md` sections 3 to 6 and `ACCEPTANCE-SCENARIOS-v5.md`.
- Say: The spec owner wrote the scenarios before any code. The builder never edits them. Two of them are the organizer's own. M1: a delayed quote is labeled delayed and never called real time. S5: a stale weather result can't overwrite a changed destination's card.
- Ask each pair to pick one scenario and name the edit to the product that would make it fail.

### 14:05 What Mantle compiles can be graded offline (30 min)
- Participants (already on `74adca16483ed8444a2c89121bc63cc4bac52332` from the addendum), from `workshops/software-factories-masterclass/brief-me-before-i-fly`:
  1. Read `project/skills/briefing/skill.md`.
  2. Write down which of the fourteen edits the suite will reject.
  3. `MANTLE_PROJECT=$PWD/project PYTHONPATH=../factory ../factory/.venv/bin/python acceptance/a6_briefing.py` (15 tests OK), then `../factory/.venv/bin/python grade_variants.py project` (baseline ACCEPT, fourteen REJECT, each with its failing check).
- Land it: the engine reports nothing about wording; the protected suite does. A wording check accepts any edit that keeps the checked phrases: find one it accepts. It grades what Mantle will load, not the server, the data or a model.

### 14:45 A specialist behind one tool is advice (30 min) [PRODUCT]
- Show the one tool `briefing(action=start|get|revise)` and the Core boundary behind it. At the participant commit the specialist transport is scripted. A real Mantle model over those replay results is a separate check. Show a real managed OpenAI Agents run only if the organizer chose the separate live worker and that exact path has passed the facilitator check. Name the path you're showing. Keep the REPLAY labels on the constructed flight data even if a model or a managed agent is live. Don't transfer offline or Mantle evidence to the managed Agents leg. Nothing here has run against the real Agents service before today.
- Show that numbers on the cards come from validated data, not from the model's prose: the unchecked `9999` case in the author's control is replaced by the checked card.
- Land it: the specialist investigates; the application validates; the card is the evidence. The briefing id is a capability: whoever holds it can read the briefing, and it is not engine-sender isolation.

### 15:15 The honesty rules are acceptance scenarios (25 min) [PRODUCT]
- Show the recorded product acceptance results for the class commit: 10 of 10 checks passed on the running replay service, through its public MCP tool only. They are the author's recorded results, and the test file isn't in this repository, so don't run it in class. For the actual Mantle conversation check, follow section 7 of the companion project README and record what you see. Don't show a mutant unless you can name its command and the checks that fail.
- Run the contract checks on the pinned Core wheel, from this folder, with the worker interpreter: `../../../examples/mantle-flight-briefing-openai-agents/worker/.venv/bin/python -B contract/accept_contract.py` (20 tests) and the same with `contract/accept_contract_s5e.py` (2 tests). A bare-string `replaces` value was a defect in the first wheel.
- Land it: protected scenarios give the factory a repeatable acceptance check. Independent review and the receiving workflow still need their own evidence.

### 15:50 The second act: the next feature, specified before it's built (30 min) [PRODUCT]
- Say first: the market watchlist is the next feature. No adapter and no coding-agent run for it exist in this repository yet. This block teaches the specification of a feature that isn't built yet.
- Show the closed `market_watchlist` component in the spec and the five market scenarios M1 to M5. Show the factory gate: M1 to M5 plus S2, S3, S5 and S6.
- Ask each pair to write down what a coding agent's change must do to pass the five scenarios, and which edit to the acceptance files or the other adapters the gate would catch (M4, checked by hash).
- Land it: the spec owner writes the gate before any code, and the builder can't edit it.

### 16:20 What this does not show (10 min)
- Say: This is replay data of a constructed flight. We make no claim about model behavior. There is no live traffic. The cards aren't a Mantle feature. We had no live Agents API result before today, unless the facilitator's own run showed one. Voice isn't evidence.
- Leave with: the spec owner, the protected scenarios, and the one place the product can still fail.
