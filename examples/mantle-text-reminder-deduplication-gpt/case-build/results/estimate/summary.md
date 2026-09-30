# reminder-deduplication-gpt-text: run summary

- Case: `reminder-deduplication`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T19:16:47Z to 2026-09-30T19:17:24Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 3; turn latency p50 6828.8 ms, p95 11343.4 ms, max 11343.4 ms
- LLM calls: 8 (2.67 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 23466 prompt (10752 cached), 365 completion (of which 70 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; sent_claim: 0; reminder_reference: 2
- Case metric reminders_delivered: 1 over 1 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.079896 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-confirm-after-resolve | correction | pass | load_patient_profile→None, send_appointment_reminder→succeeded, list_appointments→read, record_reminder_reply→not_confirmed, record_reminder_reply→confirmed | 11343, 5469, 6829 | 0.079896 |

Synthetic scenario: Cedar Clinic and all its data are fictional. The target channel is Twilio SMS; every run is web chat over local REST. Pass conditions read tool calls, arguments and results from the tracker only. sent_claim is read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (obsolete or duplicate reminders delivered, over queued reminder attempts), receipt delivery and unbacked send claims from the stored trackers. The agent has no engine confirmation gate: the reminder's own question is answered in the patient's next message, so utter_on_user_denial does not apply. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
