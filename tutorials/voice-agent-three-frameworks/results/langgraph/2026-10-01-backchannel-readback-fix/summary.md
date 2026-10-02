# langgraph: backchannel-readback replay, 2026-10-01-backchannel-readback-fix

- Run: 2026-10-01T15:47:00+00:00 to 2026-10-01T15:47:41+00:00; 1 replays; spend 0.0220 USD (model 0.0174, speech-to-text 0.0046)
- Scenario `backchannel-readback`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Yeah.', 'anchor': 'read_back', 'ends_s_after_anchor': 2.0, 'spoken_s': 0.53}]}
- Server folder: `langgraph-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `langgraph-backchannel-readback-20261001T154700-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yeah.': False. 'Yeah.' sent before the first read-back: False (read-back -2.01 s after it).

```text
   2.50  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.50  bot_turn_ended
   8.73  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.73  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
  10.49  bot            One moment while I check your details.
  19.96  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  19.96  bot_turn_ended
  21.97  SENT           Yeah.
  21.97  user           Yeah.
  25.52  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  25.52  bot_turn_ended
```
