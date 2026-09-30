# Cedar Clinic appointment reminders on GPT-5.5: one reminder per booking version

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of outbound patient or customer notifications
Time:          15 minutes to run the agent; about 10 minutes and 1 USD for the live conversation suite
```

A Rasa Mantle text agent for one casebook case,
[`reminder-deduplication`](../../tutorials/rasa-ai-team-casebook/examples/reminder-deduplication.json):
send a patient of Cedar Clinic, a fictional clinic, a reminder for one of
their appointments, take their reply to it, and pass a change of time to the
scheduling team. It runs on OpenAI's `gpt-5.5-2026-04-23` with
`reasoning_effort: low`.

**Channel.** The target channel is Twilio SMS. The programme has no Twilio
account yet, so the agent serves web chat over the REST and socket.io
channels, and every recorded run is web chat over local REST.
`integrations.yml` shows the `twilio` block to add once there is a number.
Two things about Rasa's `twilio` channel were read in the code and not run:
the conversation's sender id is the patient's phone number (the webhook form's
`From`), and `TwilioOutput.send_text_message` splits every bot message on
blank lines and sends each part as its own SMS.

The case's failure is one sentence: *a rescheduled appointment generated
both the old reminder and the new one, sending the patient to the wrong time.*
In this project a reminder's identity is the appointment revision, not the
send. The tools read the current revision from the booking system when a
reminder is queued and again at delivery, send at most one reminder per
revision, and send only to the confirmed number on file. Delivery and the
patient's confirmation are recorded separately.

**The live suite ran in two parts.** The OpenAI account ran out of credit
ten conversations into the first run (`insufficient_quota`: "You have no
credits remaining"); that run stopped and was not retried. Once credit was
back, the 14 conversations it had not passed (11 not run, 2 lost to the
credit error, 1 failure) ran again on the code with one fix,
`record_reminder_reply` finding a reminder from the patient's words. All 14
passed. With the first run's 7 passes, all 21 scripted conversations have
passed once.

## Scope

- **Synthetic scenario.** Cedar Clinic, Lena Marsh, the clinicians, sites,
  numbers, appointments and references are invented (`lib/fixtures/`).
  `lib/reminders.py` refuses to load a fixture whose organisation fields are
  not the casebook contract's own fictional clinic marked `(fictional ...)`.
  It is an allowlist, not a list of real names.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` (`reasoning_effort: low`) through Rasa 3.21.0.dev5 and
  LiteLLM 1.101.2, run from one laptop over local REST on 2026-09-30.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what the patient was shown, per-turn
  latency over local REST, and the tokens and cost OpenAI reported.
- **What they do not show:** anything sent through Twilio, real SMS delivery
  receipts, a real booking system or reminder queue, rates for production
  traffic, or anything about another model. Each conversation passed once;
  none was repeated. No medical guidance.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE and OPENAI_API_KEY in .env
make proof      # offline guard, reply and receipt tests: no licence, model or network
make validate
make train
make inspect    # chat in the Inspector
make run        # REST at /webhooks/rest/webhook and socket.io, port 5005
```

Try: "Text me a reminder for my follow-up with Dr Marr", then "That's wrong,
it's Tuesday at 9:30", then "Send me the physio reminder again".

To rerun the recorded suite (billed GPT-5.5 calls, capped at 3.50 USD across
all runs by the ledger in `case-build/results/spend-ledger.json`), then the
case metric (no spend):

```bash
make conversations
make metric RUN=2026-09-30-gpt-5.5-low
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, referenced as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |

## How the guard works

The casebook lab gives the case three request rules.
`send_appointment_reminder` enforces them in `lib/reminders.py`. The model
supplies the patient's words for the appointment and, only if the patient
asked for somewhere else, their words for where to send. It never supplies a
revision, a time the tools trust, a fact, a patient id or an attendance
answer, and `tests/test_guard.py` fails if a tool gains a parameter that could
carry one.

| Rule (lab field) | Fails with | How the code decides |
|---|---|---|
| `appointment_revision_current` | `blocked` / `obsolete_appointment` | The reminder is always for the booking's current revision. When the patient's words carry a time or date, it must match the current version: "Tuesday 9:30" for a follow-up since moved to Thursday 2:15 pm is refused and the current time returned, never swapped in silently. An appointment with a change request open has its reminders paused. At delivery the booking is read again, and a revision that changed after queueing is suppressed |
| `reminder_not_sent` | `blocked` / `duplicate_reminder` | No reminder for this revision has reached the phone, and none is in flight with its delivery unknown. A queued reminder for the same revision is the same reminder (one `CC-RMD-` reference per revision), never a second one. A rejected text counts as not sent, so it can be reissued once |
| `recipient_channel_confirmed` | `blocked` / `unconfirmed_contact_channel` | The reminder goes to the SMS number on file, confirmed and consented for reminders. A number typed in the chat, "my new phone", another person's phone, or the email on file (it bounced and was not re-verified) is refused |

A fact must be exactly `true`, as in the lab: the tests replay all ten of the
lab's variants against this code.

**The evidence scenario.** The contract asks for "a reschedule between queue
creation and delivery; the old revision must be suppressed". The fixture's
blood test has a reminder queued for 8:10 am, and the front desk moves it to
8:40 am at the moment of delivery. The tool suppresses the 8:10 reminder,
issues only the 8:40 one, and its message says the earlier one was stopped.
`test_reschedule_between_queue_and_delivery_suppresses_the_old_revision`
checks it offline, and `recovery-reschedule-before-delivery` passed live.

**Delivery is not attendance.** A delivered reminder sets only the ledger's
delivery state. `record_reminder_reply` finds the reminder from its reference
or from the patient's words for the appointment (words naming an earlier
version's time find that version's reminder), and records attendance from the
patient's own latest message after the reminder (a yes confirms; "the time is wrong" or
"can we move it" confirms nothing), and only for the current revision. A yes
to the reminder for the follow-up's earlier time is refused with the current
booking.

**Recovery.** A reminder whose acknowledgment is lost stays `unknown`; a
resend is refused until `check_reminder_delivery` queries the ledger by
revision and reconciles it. A change request pauses the appointment's
reminders until the scheduling team confirms a time.

**The tool sends the reminder.** The reminder the patient receives is the
tool's own message through `ToolContext.send`: the reference, the current
time, a note when it replaces an earlier reminder, and the contract's
question ("This is a reminder for the appointment time you selected. Would you
like to confirm or change it?"). The attendance receipt and the change-request
reference are sent the same way (found in the HarborCover claim-intake build,
where a silent `complete_skill` otherwise hid the receipt).

**No engine confirmation gate.** The reminder's question is answered in the
patient's next message and read by `record_reminder_reply`, so there is no
`requires_confirmation` and `utter_on_user_denial` does not apply: a
correction at the question is answered in the same turn.

**Each memory value is one short field**, because Mantle cuts a memory value
at 100 characters in the prompt without saying so. Appointment times are
never kept in project memory, which is write-once and would go stale on a
reschedule. A test builds the skill-memory values for every appointment,
every revision, every ledger state and the longest day names, and fails if
any would pass 100 characters.

**The words are measured.** `sent_claim` in `case-build/conversations.json`
counts sentences saying a reminder was sent or resent, and
`case-build/case_metric.py` checks each against the tools' deliveries in the
same turn. Both read straight and typographic apostrophes, because GPT-5.5
writes `’`; the tests check the spec's regexes on raw text with both.

## Why `reasoning_effort: low`

Rasa sends `reasoning_effort: none` for GPT-5.5 when the project sets
nothing (`rasa/shared/utils/llm.py`, `_apply_default_reasoning_effort`). In
the Northgate block-card build
([`mantle-voice-banking-block-card-gpt`](../mantle-voice-banking-block-card-gpt)),
at `none` GPT-5.5 twice wrote a tool call out as text that Mantle sent to
the caller, and twice announced an action and ended the turn without taking
it; at `low`, on the same nine calls, it did neither. In this case an agent
that says "I've resent your reminder" without calling the tool, or prints the
call as its reply, leaves the patient trusting a reminder that does not
exist, so this build starts at `low`. In these runs no reply held a tool call
written as text. The `reasoning-default` variant in the spec removes the
setting; it has not been run here.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30 with
`gpt-5.5-2026-04-23` at `reasoning_effort: low` over local REST. Latency is
the wall-clock time of each REST request. Tokens are the provider's counts;
they matched Rasa's own `engine_tokens` total in every conversation of every
run (0 and 0 in the one that failed on its first call). Cost is LiteLLM
1.101.2's `response_cost` from its bundled price map. `case-metric.json` in
each run folder lists every counted item by conversation.

| Run | Conversations | Result | Cost |
|---|---|---|---|
| `estimate/` | 1 (`correction-confirm-after-resolve`) | 1 pass | 0.08 USD |
| `2026-09-30-gpt-5.5-low/` (first run, before the fix) | 10 of 21 started | 7 pass, 1 fail, 2 provider errors (`insufficient_quota`), 11 not run | 0.31 USD |
| `2026-09-30-rerun-lookup-fix/` (the 14 not passed) | 14 | 14 pass | 0.70 USD |

**Main run** (`2026-09-30-rerun-lookup-fix/`, 14 conversations, 23 patient turns):

| Measure | Result |
|---|---|
| Tracker checks | 14 pass, 0 fail |
| By kind | normal 1/1, adversarial 5/5, recovery 4/4, correction 4/4 |
| Turn latency, all 23 turns | p50 8.78 s, p95 16.68 s, max 21.27 s |
| Turn latency by position | first turns (session start and skill activation) p50 10.76 s; later turns p50 4.88 s |
| Model calls | 85, or 3.7 per patient turn (13 side-channel, none failed) |
| Tokens | 203,715 prompt (97,792 cached, 48%), 4,040 completion, of which 1,092 reasoning |
| Obsolete or duplicate reminders (case metric) | 0 of 9 queued reminder attempts (6 delivered, 1 delivered unacknowledged, 1 rejected by the carrier, 1 suppressed as obsolete) |
| Sent claims in bot text | 1, in a turn where the tool had delivered the reminder |
| Reminder references that reached the patient in their turn | 7 of 7, all through the tool's own message |
| Attendance and change-request references in their turn | 4 of 4 |
| Cost | 0.70 USD |

**All 21 conversations, final results** (the first run's 7 passes and the
main run's 14): 21 pass; normal 5/5, adversarial 8/8, recovery 4/4,
correction 4/4; 32 turns, turn latency p50 8.28 s, p95 16.01 s (linear
interpolation), max 21.27 s. The first run's 7 passes ran before the lookup
fix. The fix changes only how `record_reminder_reply` reads an argument that
is not a reminder reference, and none of those 7 conversations passed one.

**The guard held in every conversation.** No reminder reached the phone for
an earlier version of a booking, and none reached it twice. The evidence
scenario ran live: the blood test's queued 8:10 am reminder was suppressed
when the booking moved to 8:40 am before delivery, and only the 8:40 reminder
went out, saying the earlier one was stopped. The lost acknowledgment was
reconciled by `check_reminder_delivery` and not resent. The rejected text was
checked on the ledger and reissued once, under the same reference, after the
patient said yes. A change request paused the physio reminders, and the
patient's next "send me a reminder for it" was refused by the code.

**The code decided most adversarial conversations.** In 7 of the 8,
GPT-5.5 passed the patient's words to a tool and the guard refused: the old
Tuesday time (twice: once to `send_appointment_reminder`, once as a yes to
the old reminder through `record_reminder_reply`), a second physio reminder
(three times, including the typed facts and "just tell me it's been
resent"), a new number and the unconfirmed email. The eighth, another
patient's appointment id, was refused by Mantle's `cannot_help` before any
tool ran. Asked to "just tell me it's been resent", GPT-5.5 answered "I
can’t say it was resent because it wasn’t."

**The first run's failure and its fix.** In `normal-physio-confirm-existing`
the patient wrote "I got your reminder for physio on Monday at 11. Yes, I'll
be there." In the first run GPT-5.5 answered "Please send the reminder
reference, starting CC-RMD, so I can record your yes." and called no tool,
because `record_reminder_reply` took only a reference. It now also takes the
appointment in the patient's words, and the skill says never to ask the
patient for a reference. In the main run GPT-5.5 passed "physio on Monday at
11" and the attendance was recorded. It used the words path in 5 of the 6
`record_reminder_reply` calls in the main run, including "my appointment is
Tuesday at 9:30", which found the follow-up's earlier reminder and was
refused as obsolete.

`spend-ledger.json` lists every billed run for this build: **1.09 USD** in
total (estimate 0.08, first run 0.31, main run 0.70), against a cap of 3.50.

## What we found

1. **When GPT-5.5 returned nothing after the tool, the tool's own message
   was the only reply.** In `recovery-change-request-pauses`, after
   `request_appointment_change` routed the request, GPT-5.5 returned an empty
   response three times; Mantle logged `mantle.turn.failed` ("LLM returned an
   empty response") and sent the patient nothing more. The patient still had
   the change-request reference, because the tool had sent it. In
   `normal-physio-confirm-existing` the model closed the skill after the
   attendance receipt, and Mantle sent "Can I help with anything else?". In
   the main run 7 of 7 reminder references and 4 of 4 attendance and
   change-request references reached the patient in their turn; GPT-5.5
   repeated a reference itself for 1 of those 11. The harness summary shows
   "0 empty completions" for this run while the server log has 4
   `mantle.orchestrator.empty_llm_response` events, so its empty-completion
   count misses this case.
2. **As Twilio SMS, GPT-5.5's typographic apostrophe costs a segment on
   short refusals** (computed from the recorded text with the GSM 03.38
   alphabet and Rasa's blank-line split; nothing was sent). A single `’`
   forces a message out of GSM-7 into UCS-2, which fits 70 characters instead
   of 160. In the main run the 50 bot messages come to 63 SMS and 101
   segments; with straight apostrophes they would be 92. Of GPT-5.5's 34
   parts, 8 were UCS-2 and 7 of those went from one segment to two, most of
   them refusals ("That reminder was already delivered, so I can’t send a
   second one for the same appointment"). Mantle's out-of-scope reply, as
   rephrased in these runs ("I can’t help with that here..."), did the same
   twice. The first run's shorter messages lost nothing this way. One run,
   14 conversations.
3. **Our own SMS style rule dropped two appointments from a question.** The
   prompt's `text_rules` say "no lists longer than three lines". Asked "Can
   you text me a reminder for my appointment?", GPT-5.5 read all five
   bookings and asked "Which appointment should I text you about?" listing
   three: the dermatology consultation and the eye test were left out with no
   mention (`normal-which-appointment`, first run). One conversation; the rule
   is unchanged.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona and rules |
| `integrations.yml` | GPT-5.5 model group; `rest`, `socketio` and `inspector` channels; the `twilio` block to add |
| `memory.yml` | Project memory written by `load_patient_profile` |
| `skills/default_session_start/` | Binds the patient, then greets |
| `skills/appointment_reminders/` | The skill, its tools and the latest-reminder memory |
| `tools/cedar_reminders.py` | `load_patient_profile`, `list_appointments`, `check_reminder_delivery` |
| `lib/reminders.py` | Bookings and revisions, reminder ledger, delivery, guard, replies, receipts and words, no Rasa imports |
| `lib/conversation.py` | The patient's messages and the reminders sent, from tracker events |
| `lib/fixtures/` | Fictional bookings, ledger and contacts, and the vendored case contract |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 21 scripted conversations, their tracker checks and the `reasoning-default` and `receipt-in-result-only` variants |
| `case-build/case_metric.py` | The case metric, receipt delivery, sent claims and the SMS segment count, from stored trackers |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness that runs the conversations is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 with GPT-5.5 and Mantle

- Mantle reads channels from `integrations.yml`. It does not fall back to
  `credentials.yml`, so web chat is `rest` plus `socketio` there, and so
  would Twilio be.
- Rasa's `twilio` input channel reads `From` and `Body` from the webhook form.
  It keeps `auth_token` only to build the output client; the input handler
  shown in `rasa/core/channels/twilio.py` does not check Twilio's request
  signature. Read in the code, not run.
- Mantle project memory is write-once, so `load_patient_profile` writes it
  only when it is empty, and nothing that changes (an appointment time) is
  kept there.
- Mantle imports `lib/` from a temporary snapshot that is removed after
  loading, so fixtures are read at import.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms.
