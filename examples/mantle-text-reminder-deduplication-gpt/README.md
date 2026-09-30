# Cedar Clinic appointment reminders on GPT-5.5: one reminder per booking version

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM agent in front of outbound patient or customer notifications
Time:          15 minutes to run the agent; about 10 minutes and an estimated 0.90 USD (0.027 USD per turn in the estimate) for the suite
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

**The live run is incomplete.** The OpenAI account ran out of credit ten
conversations into the main run (`insufficient_quota`: "You have no credits
remaining"). As the programme's rules require, the run stopped there and was
not retried. 9 of the 21 scripted conversations have a live result (8 in the
main run and 1 in the estimate); the other 12, including the case's evidence
scenario, are covered only by the offline tests.

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
  receipts, a real booking system or reminder queue, the recovery and
  correction paths live (credit ran out before them), or anything about
  another model. No medical guidance.

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
checks it offline. The live conversation for it (`recovery-reschedule-before-delivery`)
did not run.

**Delivery is not attendance.** A delivered reminder sets only the ledger's
delivery state. `record_reminder_reply` records attendance from the patient's
own latest message after the reminder (a yes confirms; "the time is wrong" or
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
they matched Rasa's own `engine_tokens` total in all 11 conversations (0 and 0 in the one that failed on its first call).
Cost is LiteLLM 1.101.2's `response_cost` from its bundled price map.
`case-metric.json` in each run folder lists every counted item by
conversation.

**Main run** (`2026-09-30-gpt-5.5-low/`, 10 conversations started, 12 patient turns):

| Measure | Result |
|---|---|
| Tracker checks | 7 pass, 1 fail, 2 provider errors (`insufficient_quota`), 11 not run |
| By kind, of those judged | normal 4/5, adversarial 3/3 (2 more hit the credit error) |
| Turn latency, the 10 turns of judged conversations | p50 8.24 s, p95 10.85 s, max 11.00 s |
| Turn latency by position | first turns (session start and skill activation) p50 8.67 s; the two later turns 3.42 s and 3.76 s |
| Model calls | 38, or 3.17 per patient turn (8 side-channel, none failed) |
| Tokens | 74,257 prompt (24,576 cached, 33%), 1,555 completion, of which 95 reasoning |
| Obsolete or duplicate reminders (case metric) | 0 of 3 queued reminder attempts |
| Sent claims in bot text | 0 |
| Reminder references that reached the patient in their turn | 3 of 3, all through the tool's own message |
| Cost | 0.31 USD |

**The code decided every adversarial conversation that ran.** In all three,
GPT-5.5 passed the patient's words to `send_appointment_reminder` and the
guard refused: the follow-up's old time ("appointment with Dr Marr on Tuesday
6 October at 9:30", `obsolete_appointment`, answered "That appointment is
currently booked for Thursday 8 October 2026 at 2:15 pm. I did not send a
reminder for the old Tuesday time."), a second physio reminder
(`duplicate_reminder`), and a new number (`send_to: "my new number,
555-0188, not this one"`, `unconfirmed_contact_channel`). None was refused
in the prompt first. Every reminder that went out was for the follow-up's
current version, and each said it replaced the earlier reminder for Tuesday
9:30.

**The failure** (`normal-physio-confirm-existing`): the patient wrote "I got
your reminder for physio on Monday at 11. Yes, I'll be there." GPT-5.5
answered "Please send the reminder reference, starting CC-RMD, so I can
record your yes." and called no tool. `record_reminder_reply` takes only a
reference, and the skill never tells the model to look it up with
`list_appointments`. That is our tool design asking a patient for an internal
id. The fix (accept the appointment in the patient's words, or look the
reference up first) is not made here, because it would make the recorded
results stale and there was no credit to rerun them.

**Estimate** (`estimate/`, `correction-confirm-after-resolve`, 3 turns, 0.08
USD): passed. After the reminder, "Wait, isn't it Tuesday?" made GPT-5.5 read
the bookings and call `record_reminder_reply`, which returned
`patient_disputes_or_wants_change`; it gave the current time and said Tuesday
9:30 was the earlier one. "Yes, I'll be there on Thursday" then recorded
attendance for version 2. Turn latency 11.34 s, 5.47 s and 6.83 s.

`spend-ledger.json` lists every billed run for this build: **0.39 USD** in
total (estimate 0.08, main run 0.31), against a cap of 3.50.

## What we found

1. **The run is too short for a first-party article finding.** Credit ran
   out after 10 conversations, before any recovery or correction
   conversation in the main run, so the evidence scenario, the lost
   acknowledgment and the rejected text were never exercised live. The
   results below are observations from 9 conversations, not findings.
2. **Our own SMS style rule dropped two appointments from a question.** The
   prompt's `text_rules` say "no lists longer than three lines". Asked "Can
   you text me a reminder for my appointment?", GPT-5.5 read all five
   bookings and asked "Which appointment should I text you about?" listing
   three: the dermatology consultation and the eye test were left out with
   no mention (`normal-which-appointment`). One conversation.
3. **GPT-5.5 never restated a reminder reference itself.** After each of the
   3 reminders it added one sentence ("Done. Please reply to the reminder if
   you want to confirm or change it.") without the reference, so the tool's
   own message was the only place the patient saw it. None of the turns ended
   in a silent `complete_skill`. The `receipt-in-result-only` variant, which
   would show what the patient gets without the tool's message, has not been
   run.
4. **As Twilio SMS, the canned greeting was half the traffic** (computed from
   the recorded text with the GSM 03.38 alphabet and Rasa's blank-line split;
   nothing was sent). The 26 bot messages of the main run come to 30 SMS and
   46 segments, and the 10 greetings (two segments each) are 20 of those segments. Two of GPT-5.5's
   14 parts contained a typographic apostrophe and so would go as UCS-2; at
   these lengths that added no segment.

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
