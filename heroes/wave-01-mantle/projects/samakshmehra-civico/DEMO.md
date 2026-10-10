# Civico: submission and recording guide

Civico helps a caller report a civic problem, join an existing report, and follow
up using the same reference. The current sample directory covers Ghaziabad;
wards, officers, contacts and deadlines are fictional demo records.

## What to show in Rasa

| Behaviour | Rasa feature | Evidence on screen |
|---|---|---|
| Accept issue and location in either order | `ordered_block`, tool-owned memory | `capture_report` saves all volunteered details |
| Route from locality/PIN without ward questions | Local lookup inside `capture_report` | Unique match reviewed in the final summary; ambiguous matches clarified |
| Repair a detail without restarting | `revise_report`, tool-owned memory | Old approval cleared; corrected summary |
| Join the same incident | `execute_tool`, `requires`, confirmation | Duplicate question, then one supporting report |
| Approve a database write | `requires_confirmation` | Nothing filed until explicit approval |
| Return a usable reference | `context.send` | Character-by-character reference after successful write |
| Track and escalate | Shared tools, conditional `next`, date checks | Original reference retained; target changes |
| Handle a failed write | `on_failure` | Honest register-unavailable response |

The LLM handles language and tool selection. Rasa controls the flow; Python
validates writes and computes routing and deadlines. SQLite makes later follow-up
possible. This is the project explanation to use in the submission.

## Start a recording

```bash
cd path/to/civico
make verify
make test
make train
make inspect
```

`train` validates and packages the skills; it does not train a new language model.
`test` runs the local regression suite. `inspect` opens the conversation debugger
with text and voice. The REST server is `make run`, on port 5007.

Keep the conversation and Inspector tools/memory visible. Hide terminals or
panels containing keys. Use the fictional callback number below.

## Main recording: report with a correction

Speak each line when it answers the agent's current question. If the agent asks
something extra, answer that question; the script is not a fixed turn protocol.

1. “I want to report garbage bags left for three days outside the Juniper School gate in Indirapuram.”
2. When asked for a callback: “Nine zero zero zero zero zero zero zero zero one.”
3. At the submission question: “Actually, it's at the park gate opposite the school.”
4. After the corrected summary: “Yes, please file it.”
5. After receiving the reference: “What is the status of that complaint?”

If an earlier run has already reported garbage in this ward, say whether it is
the same incident. For a clean run, use a separate demo database as below.

Suggested opening narration: “Civico is a civic complaint voice demo built with
Rasa Mantle. I'll report a problem, correct a location, and track the report.”

Suggested closing narration: “Rasa controls the collection and confirmation.
The tools choose the demo ward and department, and the saved reference works
for later follow-up.”

## Second short clip: an existing incident

Report drainage in Vaishali. Give the landmark “outside the corner shop on the
main road”, describe the overflow, and use `9000000000` as the callback number.
When offered the existing incident, say “Yes, that's the same drain.” After
the summary, approve adding your details once. You should hear the shared reference
`C I V one zero zero four`. No extra complaint is created.

In a new conversation, ask to check complaints using `9000000000`. The shared
report should be available even though that number did not file the original.

## Other useful cases

Location-first example (the caller does not have to follow a form):

1. “I want to file a complaint.”
2. “It's near Juniper Heights, Vashali, Ghaziabad.”
3. “The street light is not working.”
4. “It's beside the metro station on Vikas Marg.”
5. “Nine zero zero zero zero zero zero zero zero zero.”
6. Approve the final summary. If offered an earlier report, say whether it is
   actually the same incident before approving.

The location in step 4 should be accepted even if Civico is asking for the
callback number. It must not be rejected as an invalid problem description.

- Unclear locality: give two answers such as “outside our lane” and “I don't know
  the colony name”. Show the grievance-cell fallback, then finish the report.
- Overdue complaint: on fresh seed data, ask for `CIV1002` and approve escalation.
  It keeps its reference and receives the next level's target date.
- Failed write: use `make demo-failure`. Confirm a new report and show the failure
  response; no new complaint should exist.

For a fresh register without deleting existing reports:

```bash
demo_dir=$(mktemp -d)
CIVICO_DB_PATH="$demo_dir/civico.db" .venv/bin/rasa inspect
```

## Before publishing

Current verification: see FINDINGS.md for the latest dated test counts and live
results. The rebuilt model packages successfully;
direct REST rehearsals verified one-summary filing, corrected-landmark filing,
and duplicate attachment. The September 10 voice flow has not yet been verified
with a fresh microphone/TTS pass. Historical tracking checks remain in FINDINGS.md.
See FINDINGS.md for the saved references and the beta issues found during testing.

The Wave 01 directory requires a self-contained project with a reproducible
lockfile, an `.env.example`, clear run instructions, and an honest account of
what remains. The parent community repository provides the Apache 2.0 licence.

- Add your recording link and project row to the Wave 01 index in the submission PR.
- Record a fresh voice pass of this build; local tool tests do not verify microphone
  transcription, TTS or Inspector audio/text timing.
- Intermittent beta behavior remains documented: raw tool JSON in a reply and
  unnecessary knowledge-search/resume prompts. Do not call the voice experience
  fully reliable based on the passing offline suite.
- Describe the remaining limits: fictional routing, English speech, coarse duplicate
  candidates, no municipal integration and no live human transfer.
- Report current test results separately from the historical simulation runs in
  `eval/results`. New scenario files are test plans until they have been run.
