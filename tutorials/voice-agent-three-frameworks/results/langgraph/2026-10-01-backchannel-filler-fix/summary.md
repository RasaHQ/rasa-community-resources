# langgraph: backchannel-filler replay, 2026-10-01-backchannel-filler-fix

- Run: 2026-10-01T15:46:18+00:00 to 2026-10-01T15:46:58+00:00; 1 replays; spend 0.0207 USD (model 0.0162, speech-to-text 0.0046)
- Scenario `backchannel-filler`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Okay.', 'anchor': 'first_bot', 'ends_s_after_anchor': 0.8, 'spoken_s': 0.53}]}
- Server folder: `langgraph-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `langgraph-backchannel-filler-20261001T154618-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Okay.': False. 'Okay.' sent before the first read-back: True (read-back 7.91 s after it).

```text
   2.59  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.59  bot_turn_ended
   8.58  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.58  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
  10.54  bot            One moment while I check your details.
  11.34  SENT           Okay.
  11.34  user           Okay.
  19.25  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  19.25  bot_turn_ended
  22.76  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  22.76  bot_turn_ended
```
