# rasa: backchannel-readback replay, 2026-10-01-backchannel-readback-fix

- Run: 2026-10-01T15:47:14+00:00 to 2026-10-01T15:48:00+00:00; 1 replays; spend 0.1199 USD (model 0.1158, speech-to-text 0.0041)
- Scenario `backchannel-readback`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Yeah.', 'anchor': 'read_back', 'ends_s_after_anchor': 2.0, 'spoken_s': 0.53}]}
- Server folder: `rasa-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-backchannel-readback-20261001T154714-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yeah.': False. 'Yeah.' sent before the first read-back: False (read-back -7.34 s after it).

```text
   0.12  user           /session_start
   0.13  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.63  bot_turn_ended
   8.75  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.76  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
  10.23  bot            Okay, I’ll verify your details first.
  18.34  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  21.90  bot_turn_ended
  25.69  SENT           Yeah.
  25.70  user           Yeah.
  26.98  bot            Right, I’ll send that request now.
  34.49  bot            I’m sorry, I need to read that back again before it can be sent. Please confirm after the read back finishes.
  36.64  bot_turn_ended
  36.65  user           /session_end
  41.05  bot            Can I help you with anything else?
  41.81  bot_turn_ended
```
