# Findings

## Stronger orchestrator model, September 12, 2026

- Upgraded the live Civico orchestrator from OpenAI `gpt-5.4-mini` to the full
  `gpt-5.4` model. The `gpt-5-nano` response rephraser and the separate
  `gpt-5.4-mini` simulation/judge configuration were deliberately left alone.
- Kept the prompt, skills, constraints and tool contracts unchanged so the test
  isolates the model change. Rasa and Python still own confirmation, category
  validation, routing, IDs, dates and writes.
- Preflight passed, all 150 offline tests passed, and packaging produced
  `models/20260912-001842-largo-hash.tar.gz`.
- An isolated REST smoke test accepted a complete one-sentence garbage report,
  produced one summary, paused for confirmation, called the filing tool and
  saved `CIV1005` with Indirapuram, the Juniper School gate and Sanitation intact.
  The two user turns took about 7.2 and 6.0 seconds respectively. This is one
  smoke test, not a latency benchmark or a voice-quality result.
- The installed Rasa tokenizer does not yet recognise the `gpt-5.4` name and
  logs that it uses `cl100k_base` as a fallback. This warning did not prevent the
  live model or tool calls from working, but it should be watched for long
  prompts. No Rasa vendor package was patched.

## Product experience improvements, September 11, 2026

- Friendly callback wording explains follow-up rather than demanding a digit
  count; the final review includes only its last four digits. Receipts explicitly
  identify demo assignments/targets and explain reference or callback lookup,
  without promising an actual dispatch, SMS, or follow-up call.
- Locality/PIN chooses a sample routing area; a separate incident landmark is
  still required. Initial landmark additions preserve the earlier building.
  Explicit replacement or changing locality clears the obsolete spot.
- Short gate corrections preserve building/locality without inventing a gate
  number or direction. A category correction clears the previous issue's
  description; a callback correction refreshes review without reasking whether
  the same incident exists.
- Repeated calls to prepare the unchanged summary do not speak it again.
- Added a read-only conversation scorecard and PRODUCT_ACCEPTANCE.md. Measures
  include saved reports, post-review corrections, saves after correction, empty
  replies, internal-tool text, repeated-question candidates, and first-text
  timings. Output contains no caller text/numbers/references. These counts are
  not a population success rate, and text timing is not TTS latency.

Verification: 150 offline tests pass. Model packaging succeeded:
`models/20260911-144916-intricate-major.tar.gz`.

Isolated REST rehearsals in `/private/tmp/civico-product.GviT7x/civico.db` saved
garbage report CIV1005 and corrected streetlight CIV1006, with the saved spot
`outside Juniper Heights other gate` in Vasundhara. Joining CIV1004 persisted
its own supporting landmark and retained the original target. The correction
scorecard showed one saved-after-correction, zero empty replies, zero internal
tool-text messages, and zero doubled questions within a turn. Its repeated
confirmation across turns was appropriate because the caller corrected the draft.
The final-build location-first run saved CIV1008 with Juniper Heights, metro
station, Vikas Marg and Vaishali retained together. A cancellation with callback
9000000004 left zero complaint rows. Rehearsals used port 5018; the user's
existing port 5007 server and database were preserved.

Microphone/TTS testing is still outstanding. Inspector audio-before-text ordering
passes through installed Rasa delivery code. No vendor package or unsupported
voice setting was patched; no claim that the audio issue is resolved.

## Conversational intake rebuild, September 10, 2026

The caller's voice transcript exposed a product problem the earlier tool tests
did not measure: repeated questions, category-first intake, a late recording
notice, and a description requested after the caller already said the light was
not working. Previous passing tests were not proof of a good voice experience.

Changes:

- A bare complaint request starts intake. `capture_report` accepts issue,
  locality/PIN, landmark and callback together or in any order. The caller's
  problem statement is also the description; no obligatory second description.
- Unique directory matches are provisional routing, reviewed in the final
  summary. Only ambiguous matches/PIN conflicts need a separate choice, phrased
  as localities, not ward numbers. Selection accepts locality names too.
- `near my society` is not stored as a usable landmark. Road/metro refinements
  do not erase the established locality; explicit locality changes still reroute.
- The summary is an explicit `execute_tool: prepare_report_summary` step, followed by ONE
  Rasa `requires_confirmation` prompt. `details_verified` is now tool-owned
  read-back readiness, not caller consent. Edits invalidate it and duplicate state.
  A complete correction with no matching incident refreshes the duplicate check,
  speaks the corrected summary inside the tool, then requests a fresh consent question. This
  replaced a model-spoken correction summary that sometimes skipped readiness.
- The greeting labels this as a demo. Removed the report-activation recording
  claim. Submission failures no longer automatically claim a database outage.
- Internal category, ward-lookup and callback helpers are no longer separate
  LLM tools. A live run had called them after capture_report and cleared a
  correctly saved route. `confirm_ward` is safe against redundant selection.

### What remains a beta finding

A rehearsal called `search_knowledge` to find supported categories despite the
skill already listing them. That caused the existing spurious resume prompt
described in finding 17. Added an agent-wide rule limiting knowledge search to
the caller's explicit factual questions. This is a prompting mitigation, not a
Rasa engine fix or a guarantee that the interruption issue cannot recur.

Rasa's orchestrator emits text accompanying tool calls as filler. The new agent
rules request tool-only calls without spoken preambles. The pasted doubled audio
has NOT been reproduced or verified fixed on a microphone/TTS channel. Installed
voice code also delivers audio before some Inspector tracker updates; this is
relevant to audio/text ordering, but source inspection is not a microphone test.
No installed Rasa package was patched.

One clean rehearsal also emitted a raw activation JSON object as a bot reply,
and another had an empty response after choosing an existing incident. Added
an explicit no-internal-JSON rule, and made summary execution deterministic.
The JSON issue is the intermittent behavior already documented in finding 21;
the added rule is not proof that it is eliminated.

### Verification

- 135 offline tests pass; project preflight passes; model packaging succeeds.
- Intermediate isolated REST runs saved a compact garbage report (`CIV1006`),
  a corrected Vasundhara streetlight report (`CIV1007`), and a Vaishali report
  retaining building + metro + road (`CIV1008`). Attachment saved a supporting
  report on `CIV1004`. Cancelling callback `9000000004` saved no complaint.
- One repeated correction script encountered an existing report created by its
  earlier run, so its next fixed answer no longer matched the bot's question.
  Scripted rehearsals are not a passing eval verdict; use a fresh database or
  explicitly answer same/different. Updated the demo scripts accordingly.
- Observed REST latency was roughly 3–15 seconds, higher on multi-tool turns.
  Voice latency, audio duplication, interruption and screen timing need a fresh
  manual pass before recording the final showcase.
- Final packaged model: `models/20260910-235348-visible-sanding.tar.gz`.
- Final-build REST checks in `/private/tmp/civico-final.8Q1CqR/civico.db`:
  corrected pothole `CIV1007` saved at the park gate opposite the school in
  Vasundhara, with one corrected-confirmation question; garbage `CIV1008`
  saved at the Juniper School gate in Indirapuram after a single summary/consent.
  These final turns took approximately 3.5–5.5 seconds. Earlier in this clean
  database, attachment to `CIV1004` persisted, while cancellation saved zero rows
  for `9000000004`. Temporary test servers were stopped after verification.

Existing server on port 5007 and existing complaint rows were preserved.
New rehearsal rows live only in temporary databases. Historical simulator
results below have not been rerun against this rebuilt conversation.

## Submission review, September 7–8, 2026

Application fixes in the updated `civico` folder:

- Supporting reports now have their own SQLite table. Each callback number can
  attach once, retaining the description and exact landmark. Resolution notes
  and the original deadline remain intact, and phone lookup includes attachments.
- Attachment requires summary approval and a Rasa confirmation prompt, then speaks
  the saved shared reference via `context.send`.
- Phone-list selection uses the exact displayed list. Previously it queried the
  calling number again even when the caller had searched a different number.
- Repeat callers are included in duplicate detection. Reports in the general
  grievance queue are excluded because that queue is not a location.
- Complaint ID allocation and insertion share one SQLite write transaction.
- Filing rechecks required details and fixed routing data. Repeated invocation
  within the same report returns its existing reference.
- `revise_report` handles initial details and later corrections. Location/category
  changes invalidate duplicate selection and summary approval.

### What the live correction runs exposed

Local tests passed while an early live build read a corrected landmark back and
then exited without filing. The tracker showed the native `correct` tool
rewinding a collect step, followed by `complete_skill`, despite no saved reference.
Another run treated a tool-written `details_verified=False` as a past decision
to correct and attempted to replay the wrong producer.

The report now keeps landmark and description capture in tool-owned steps,
clears approval to `None`, and uses explicit `execute_tool` branches for filing
and attachment. Both branches still pass through `requires_confirmation`.
The Rasa package itself was not modified.

An attempted generic `**corrections` argument introduced another issue: the LLM
filled it with prose. It was removed; the detail tool exposes only `field` and
`value`.

### Verification evidence

- Offline suite: 122 passing tests, including concurrent ID allocation,
  attachment idempotence, correction invalidation and alternate-phone selection.
- Model validation and packaging passed on Mantle `3.20.0.dev6`.
- Direct REST correction rehearsal saved `CIV1005` after a fresh confirmation,
  spoke its reference, named S. Kaur, and returned the two-day Sanitation target.
- Direct REST attachment rehearsal spoke `CIV1004` and persisted the supporting
  description and landmark separately, without creating a new complaint.
- Final package: `models/20260908-215615-cloudy-slider.tar.gz`. A separate REST
  conversation retrieved `CIV1005`, spoke the corrected park-gate location,
  Sanitation, S. Kaur and the September 10 target. The isolated database held
  five complaints (four seeds plus that one filing) and one supporting report.

Rehearsals used an isolated database on port 5017; the existing server on 5007
and its complaint records were preserved. These are text-channel checks, not a
new microphone/TTS test or a rerun of the historical LLM-judged scenario suite.

---

What a newcomer to the Mantle engine actually got stuck on, building Civico at
`rasa-pro 3.20.0.dev6`.

Each entry is something that cost real time, with what it looked like and what
fixed it. Several of them fail *silently* — no error, no warning, just an agent
that behaves differently from what the files say. Those are the expensive ones.

Nothing here is a complaint about the engine. Most of these are things a
reference page could say in one sentence and does not.

---

## 1. A skill with any free prose enters the prose flow, and the ordered block then becomes optional

**The big one.** Every other finding in this document cost hours; this one cost
a day, and it silently undoes the main control lever the engine offers.

Write a skill as prose plus an ordered block, referenced the way the shipped
examples do it:

```markdown
Take the caller's complaint. One question at a time.

Invoke `@block.intake` immediately.

:::ordered_block id=intake
steps: ...
:::
```

The block never runs. The stack shows:

```
flow=report_problem step=autonomous
```

`step=autonomous` means the skill is in free-form mode and the block was never
pushed. The engine offers the block to the model as an `activate` target — and
the model, already able to answer, simply answers. Six ordered steps with
`complete_when` guards became a suggestion, and the agent skipped straight to
the summary and never filed anything.

The mechanism is in `skills/catalog.py`:

> Hybrid and autonomous skills always enter the prose flow when present.
> Ordered blocks (including `main`) are reached via `call:` / `link:`, not as
> the cross-skill entry. Fully controlled skills (ordered blocks only) prefer a
> `main` block, then the first flow.

So the rule is: **prose wins over blocks for the entry point, always.** A skill
that must follow a sequence has to have *no free prose at all*, and its block
must be called `main`:

```markdown
---
name: Report a Problem
...
---

:::ordered_block id=main
steps: ...
:::
```

Then the engine enters the block itself and the stack reads
`flow=report_problem__main step=area`, holding position across turns.

Rephrasing the invocation does not help — "Work through", "Invoke …
immediately", "Do not ask anything before invoking it" all left it autonomous.
It is not a prompting problem.

The guidance to add: *if the order matters, the skill gets no prose. Put the
standing instructions on the block's `description`, and everything else into
steps.*

## 2. `@skill.` and `@block.` references are only read from free prose — never from inside a block

The direct, and expensive, consequence of finding 1.

Having made every ordered skill prose-free, the handoffs stopped working:

```
BOT  Could not continue: no such skill `escalate__main`.
```

`check_status` had `invoke @skill.escalate` in a step's `instructions:`, exactly
where the guidance for finding 1 puts everything. But the compiler builds
`referenced_skills` from

```python
prose = "\n\n".join(segment.text for segment in segments)
...
collect_prose_skill_references(prose)
```

and `segments` are *prose* segments. A step's instruction text is not scanned.
So the reference never compiles, the target is never offered to the model, and
the model — knowing the skill exists but not being allowed to name it — guesses
the compiled flow id and is refused.

The two findings therefore point in opposite directions unless you know the
third thing: **from inside a block, cross-skill handoff is a `call:` step, not
an `@skill.` mention.**

```yaml
  - id: route
    noop: true
    next:
      - if: session.who_handles_this.report_now == "yes"
        then: take_the_complaint
      - then: sign_off

  - id: take_the_complaint
    call: report_problem
```

`call:` and `link:` targets *are* collected — by
`partition_call_link_targets`, walking compiled steps — which is why this works
and the prose token does not.

This is better anyway. The branch condition is now a real condition rather than
a sentence the model has to interpret, and `RouteStep` (`noop:` + a `next:` list
of `{if:, then:}` branches) is the lever that makes it possible. It is not in
any of the shipped examples.

## 3. YAML turns a bare `yes` into `True`, silently breaking an enum

```yaml
    raise_answer:
      type: categorical
      enum_values: [yes, no]      # this is [True, False]
```

Then a route comparing `session.check_status.raise_answer == "yes"` never
matches. The caller says "yes please raise it" and is politely signed off
instead — no error anywhere, in the engine or in training.

Quote them. `enum_values: ["yes", "no"]`.

Not an engine bug — it is YAML 1.1 doing what YAML 1.1 does — but it is a very
easy thing to write in a file format where every other short string is safely
bare, and the failure is a branch that quietly never fires.

## 4. A verbatim `on_success` response ends the model's speaking turn

`on_success` looks like a way to guarantee a phrase gets said. It is also a way
to guarantee nothing else does.

```yaml
- file_complaint:
    on_success: utter_complaint_filed   # "That is filed."
```

with a step instructing the model to then read the reference number back. What
the caller heard:

```
BOT  That is filed.
BOT  Is there anything else I can help you with?
```

The tracker shows why — the model, having "spoken", went straight to satisfying
the step's completion condition:

```
bot         "That is filed."
memory_set  report_problem.reference_given = true
flow_completed report_problem__main step=file
```

It never said `CIV1005`. On a complaint line that is the one sentence the call
exists to produce.

**`on_success` is for a line that is complete in itself.** Never attach one to
a tool whose result the model still has to voice. Responses cannot interpolate
memory either — slot names are namespaced (`report_problem.complaint_id`) and a
dot in a `str.format` key is attribute access, so `{report_problem.complaint_id}`
cannot work.

Removing `on_success` was not enough on its own — see finding 3.

## 5. When the tool that runs in a step also satisfies the step, the model gets no turn to speak

With `on_success` removed, the outcome became a coin flip. Sometimes:

> Done — your reference is C, I, V, one, zero, zero, six. Ward officer
> A. Sharma will handle it, and you can expect an update by the twelfth of
> September.

and sometimes just "Do you need anything else?".

The step completes on a field the tool itself writes, so whether the model
speaks first is a race it sometimes loses.

The fix is `context.send()` from inside the tool:

```python
await context.send(
    f"That is filed. Your reference is {record['spoken_id']}. "
    f"{who}, and you should hear back by {speech.say_date(record['target_on'])}."
)
```

Deterministic, every time, with the real values in it.

**But do not reach for it everywhere.** The same change applied to
`escalate_complaint` made the caller hear the same three facts twice — once
from the tool and once from the model, which states that particular outcome
reliably on its own. `context.send` is the right tool for a line the model was
*observed to skip*, not a general policy. Which of the two applies is only
knowable by running the conversation.

## 6. Tools run from the extracted model archive, which does not contain `data/`

`rasa train` packages `tools/` and `skills/*/tools.py` into the model archive.
At run time the server unpacks that archive into a temp directory and imports
the tools from there. So this:

```python
_HERE = Path(__file__).resolve().parent

def project_root():
    return _HERE.parent          # wrong
```

resolves to somewhere under `/var/folders/...`, which has the code and none of
the data. The symptom is a `FileNotFoundError` on `wards.json` and an
`OperationalError` from SQLite, in a project where both are plainly present and
where the same call works fine from a shell.

Anchor on the working directory instead — `rasa run` and `rasa inspect` are
started from the project root — and walk up looking for a marker file. See
[`lib/paths.py`](lib/paths.py).

## 7. `import_tools` is for shared tools only, and skills cannot reach into each other

Listing a skill-local tool is a hard validation error:

```
Skill 'report_problem' lists import_tools entry 'find_ward', but it is
skill-local in skills/report_problem/tools/ — remove it from import_tools.
```

Tools in `skills/<name>/tools.py` are auto-discovered and must not be declared.
Only tools in the shared `tools/` folder go in `import_tools`.

The second half is the part that shapes the design: **one skill cannot use
another skill's local tool.** `check_status` referencing `escalate_complaint`,
and `escalate` referencing `look_up_complaint`, were both errors. A tool needed
by two skills has to move to `tools/`, which also means the memory fields it
writes must be declared in *every* skill that calls it — otherwise the write
fails at runtime in the skill that is missing them.

This is a good constraint. It just is not guessable, and it is easier to
satisfy before writing the tools than after.

## 8. Project memory is write-once

A `session.project.*` field keeps its first value for the rest of the session.
Later writes are dropped, with no error.

Days went into a boolean that would not go true before this became clear. It is
the single most useful thing to know before designing the memory layout,
because it decides the layout: project scope is for facts settled once at
session start, and everything that changes during a call belongs in skill
memory.

Civico's `memory.yml` is four fields, all caller identity, all written by
`load_caller` at session start.

## 9. `agent.yml` silently discards `name`, `description`, `rules` and `references` when they are nested under `agent:`

They are top-level keys, siblings of `agent:`. Nested one level deeper they
parse without error and are then thrown away — `AgentSpec` ignores unknown keys
and the payload builder only reads them from the top level.

In the previous version of this project eight behavioural rules sat inert for
weeks, including the one instructing the agent to tell a caller with a medical
emergency to hang up and dial 112. Nothing failed. The rules were simply not
there.

This is the finding most worth a validation warning: the shape is easy to get
wrong, the failure is invisible, and what gets dropped is exactly the safety
configuration.

## 10. `set_` is a reserved tool-name prefix

A tool named `set_category` fails to build. The error does not mention the
prefix, so the natural reading is that something is wrong with the tool itself.
It is called `record_category` here.

## 11. `llm_settable` fields get filled from earlier context, before the question is asked

`exact_spot` was an `llm_settable` field collected by an `instructions:` step.
The caller answered the *previous* question with "It is in Vaishali", and the
tracker showed:

```
report_problem.exact_spot = "in Vaishali"
```

written before the step was reached. The step's `complete_when` then read as
satisfied, and the caller was asked a question whose answer was already
recorded — from a different question.

Any field that is the answer to one specific question should be a `collect:`
step with an `utterance:`, and should not be `llm_settable` at all. Reserve
`llm_settable` for judgements the model genuinely makes across the whole
conversation. Civico has three.

## 12. Bookkeeping asked of the model in prose is followed about half the time

"Ask once more, and if that also finds nothing, call `use_general_cell`" was
obeyed roughly every other run. The rest of the time the caller — someone who
had just twice failed to name their own locality — was asked a third time.

Counting is not a judgement. It moved into the tool, which tracks attempts in
memory and, on the second miss, routes to the grievance cell itself and says so
via `context.send`. No instruction, no decision, no third question.

The general form: **if a rule can be stated as a count, a threshold or a
lookup, the model should not be the one applying it.** This is the same lesson
as replacing the geocoder, one level down.

## 13. A bare skill name in prose is a warning worth heeding

```
Skill 'check_status' mentions skill 'escalate' in prose without the '@skill.'
prefix. The mention does not compile into referenced_skills, so activating it
at runtime interrupts 'check_status' instead of delegating to it.
```

Triggered by the ordinary English sentence "Do not offer to escalate a
complaint that is not late." Reworded to "raise" and it went away. Worth
knowing that the check is on the bare word, not on the reference — a skill
whose id is a common verb will trip it in normal prose.

## 14. Skill composition works, and skill memory does not travel with it

A positive one. `check_status` invoking `@skill.escalate` pushes a real frame:

```
stack: check_status:autonomous | escalate__main:identify
```

The child skill runs its own block and returns. This is the cleanest lever in
the engine and it behaved exactly as documented on the first try.

## 15. The Inspector has no caller ID, and the first REST message is consumed by the greeting

Two small ones that cost a confused half hour each.

`default_session_start` fires on the first inbound message and returns the
greeting, so over the REST channel the caller's first *actual* sentence
disappears into it. On a phone call this is right — the agent speaks first and
the caller picking up is not a message — but any scripted test has to send a
throwaway turn first. `scripts/demo_call.py` primes with one.

There is also no caller ID in the Inspector, so a session-start tool that reads
the calling number needs a stand-in. `CIVICO_DEMO_CALLER` supplies it, which
also makes the unrecognised-caller path demonstrable (`make demo-unknown`).

## 16. Two robustness things the transcripts taught, which no amount of reading would

**A zero-argument tool gets called with a spurious argument.** The schema for a
tool with no parameters is an empty object, and the model fills it anyway:

```
find_similar_open {"": ""} -> TypeError: got an unexpected keyword argument ''
```

It retried and succeeded, so this only shows up as a wasted round trip in the
tracker. `**_ignored` on every zero-argument tool costs nothing.

**Nobody answers a one-item list with "one".** Offered a single ward and asked
to pick, callers say "yes". An agent that then asks for a digit has turned a
confirmation into an obstacle — observed three turns running:

> BOT  I found one match: Vaishali, ward 12. Is that the one?
> YOU  Yes
> BOT  I still need the ward choice, please. Say 1 for Vaishali, ward 12.

The choice parser now takes a number, an ordinal ("the second one"), or a plain
agreement when — and only when — there is exactly one option to agree to.

## 17. A references-backed answer ends the turn, so a FAQ skill cannot finish itself

Reported from a live voice call as "why did it ask me the same question three
times". Two separate causes; this is the more interesting one.

A prose skill has no completion condition, so it never completes. It stays
parked on the stack, and everything the caller says next counts as interrupting
it:

```
YOU  How long does a pothole take to fix?
BOT  A pothole or damaged road has a target of 7 days.
BOT  We were in the middle of the Civic Line FAQ. Would you like to continue
     from there, or should I drop it?
```

Nothing was interrupted. The caller asked one question and got one answer. The
engine pushes `default_continue_interrupted` because `civic_faq` is still open,
on the same turn it answered.

Worse, before the second fix below, the *next* thing the caller said was
swallowed entirely — "I want to complain about a damaged road" got "Is there
anything else I can help you with?", and the sentence after that was then read
as the problem statement.

Two fixes were tried, and neither works:

1. **An `llm_settable` `answered` flag with `complete_when`.** The model
   answers the question and does not set the flag.
2. **A one-line `finish_faq` tool**, on the theory — well supported elsewhere
   in this project — that the model calls tools reliably where it forgets
   housekeeping fields. The tracker shows why not:

   ```
   tool_executed:  search_knowledge {...}
   bot:            "A pothole has a target of 7 days..."
   flow_started:   default_continue_interrupted__main
   ```

   `finish_faq` is never called. **An answer drawn from references ends the
   model's turn**, exactly as a verbatim `on_success` response does
   (finding 4). Anything instructed to happen after answering never runs.

So a references-backed skill cannot close itself, and there is no condition to
close it on. Overriding `default_continue_interrupted` — project skills do
override bundled defaults — suppresses the symptom but also removes genuine
resume-after-digression, which a complaint line actually wants when someone
interrupts an intake to ask a question.

Left as it is, documented in the skill file. Every shipped Rasa example FAQ
skill has exactly this shape and exactly this behaviour.

## 18. Never let the model judge whether an answer is worth passing to a tool

The other half of "why did it ask me three times", and this one was fixable.

```
BOT  Which locality or colony is it in, or the six-digit PIN code?
YOU  uh
BOT  I could not match that. Tell me a nearby locality or the PIN code.
YOU  (silence)
BOT  I could not match that. Tell me a nearby locality or the PIN code.
YOU  hmm
BOT  I could not match that. Tell me a nearby locality or the PIN code.
```

`find_ward` counts failed attempts and routes to the grievance cell on the
second miss (finding 12), so this should have been impossible. It was not,
because the model never called `find_ward` at all: "uh" is obviously not a
locality, so it re-asked instead of searching. The counter never advanced, and
the loop had no exit.

On a voice channel this is not an edge case. Speech recognition emits filler,
half-words and empty strings constantly, and every one of them is a turn.

The instruction now says to pass the answer **whatever it is** — including "I
don't know", a mumble, or nothing. Two of those and the tool routes onward by
itself:

```
YOU  uh
BOT  I could not match that. Tell me a nearby locality or the PIN code.
YOU  hmm
BOT  I could not place that locality, but I can still take the complaint. It
     will go to the grievance cell, who will work out the ward.
BOT  And where exactly is it?
```

The general rule: a guard that counts attempts only works if every attempt
reaches it. Letting the model pre-filter which answers are worth passing on
silently disables the guard.

## 19. The model will answer in Devanagari if the conversation invites it

Mid-call, unprompted:

> Is that सही?

With an Indian persona, Indian place names and an English-only TTS voice, this
comes out as noise. `language: en` on the agent does not prevent it — it took
an explicit rule.

## 20. `action_executed` does not match a Mantle tool call

Writing the first evaluation scenario produced this, which took a while to
believe:

```
[FAIL] action_executed(record_category) — Action 'record_category' did not execute.
[PASS] slot_was_set(report_problem.category='pothole', ...)
```

The tool did not execute, and the slot it sets was set. Both in the same run.

`action_executed` matches classic Rasa *actions*. A Mantle `@tool` is not one:
it emits `tool_executed`, and is asserted under `goals.expected_tools` with
`tool_called:` instead. Switching six assertions over turned the same scenario
from 0/1 to 1/1 with no change to the agent.

The part worth reporting: **Rasa's own `patterns/evaluation-harness` asserts
`@tool` functions with `action_executed`.** `lookup_policy` and `get_balance`
in that pattern are both `@tool` functions, and four of its seven shipped
scenarios assert them that way. Either those assertions silently never match,
or there is a distinction here that the pattern's README does not draw.

## 21. The model can leak a raw tool call into what it says out loud

Once, mid-suite:

> agent: `{"target_id":"check_status__main"}`I'm sorry, but I can't check that
> complaint right now. Please call back on the complaint line and ask for
> status.

The JSON is a tool call that was emitted as spoken text instead of being
executed. On voice, a caller hears it read out. The agent recovered on the next
turn and answered correctly, so this is intermittent rather than fatal — but it
is the kind of thing that only shows up when something drives hundreds of turns
at the agent, which is the argument for having an eval suite at all.

Not reproducible on demand, and nothing in the project can guard against it:
the tool call never reached the engine to be constrained.

## 22. A simulated eval is an instrument with its own noise floor

The same nine scenarios, unchanged agent, two runs minutes apart: **6/9 both
times, with a different three failing.**

Most of the flapping was not the agent. It was the simulator running out of
turns before confirming a filing, or the judge marking a correct behaviour as a
violation — most memorably penalising the agent for saying "the twelfth of
September" instead of "2026-09-12", when speaking dates as dates is the
behaviour the project deliberately built.

There is a second, sharper edge: **`run_count` above 1 silently breaks any
scenario that mutates state.** The runs share one database and the framework
has no per-run reset hook. `overdue_complaint_escalates` escalates a complaint,
which resets that complaint's target date — so runs two and three find it on
time and correctly refuse to escalate it. The scenario scores 1/3 while the
agent is right all three times. Run singly with a reset in front, it is 3/3.

Across the full suite: 27 runs, 8 of 9 scenarios at 3/3, and every one of the
27 runs had the agent doing the right thing. The two "failures" were the
instrument, not the agent. That gap — between what the suite scores and what
the agent did — is the finding.

Three habits came out of it, all now in `eval/README.md`:

- **Never trust a single run.** `run_count` of 3 minimum before believing a
  failure.
- **Anything expressible as a fact belongs in an assertion, not a criterion.**
  "Dates are never read out as digits" is a `bot_did_not_utter` regex, and is
  exact and free; as a judged criterion it was neither.
- **Reset shared state between runs, and never batch a scenario that mutates
  it.** Otherwise the suite measures run order.

Worth saying plainly because the framework's own framing invites the opposite
reading: scenario files look like tests, sit next to tests, and are run like
tests. They are closer to a survey with a sample size.

---

## Two that are about the domain, not the engine

**Escalating resets the clock.** A complaint raised to the zonal officer gets
that officer's own seven days, so it cannot be escalated again immediately.
This surfaced as a failing test that turned out to be asserting the wrong
thing, which is the good way for it to surface.

**Seed relative ages, not dates.** A demo complaint stored with a fixed
`created_at` is on time the week it is written and absurdly overdue three
months later. `complaints.json` stores `days_ago` and the seeder resolves it,
so the overdue complaint is always exactly nine days overdue whenever the demo
is run.

---

## What we would tell the next person

1. Decide first whether a skill needs an order. If it does, it gets **no
   prose** and a block named `main`. If it does not, prose is fine and simpler.
2. Put anything the agent must **do** in a tool. Anything it must **say
   exactly** — a reference number, a date, a refusal — belongs in
   `context.send` or a verbatim response, not in an instruction.
3. Decide the memory scope before writing tools. Project is write-once; a
   shared tool's fields must exist in every skill that calls it.
4. Anchor file paths on the working directory, never on `__file__`.
5. Run the conversation. Every finding above was invisible in the source and
   obvious in the tracker.
