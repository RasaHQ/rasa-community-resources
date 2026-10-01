# rasa: backchannel-readback replay, 2026-10-01-backchannel-readback

- Run: 2026-10-01T15:44:03+00:00 to 2026-10-01T15:44:53+00:00; 1 replays; spend 0.1117 USD (model 0.1066, speech-to-text 0.0051)
- Scenario `backchannel-readback`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Yeah.', 'anchor': 'read_back', 'ends_s_after_anchor': 2.0, 'spoken_s': 0.53}]}
- Server folder: `rasa`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-backchannel-readback-20261001T154403-1`: guard held

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Yeah.', 'turn': 1, 'ts': 1790869472.329422}]. Sent on 'Yeah.': True. 'Yeah.' sent before the first read-back: False (read-back -7.15 s after it).

```text
   0.12  user           /session_start
   0.13  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.56  bot_turn_ended
   8.68  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.69  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
  11.12  bot            Okay, I’ll start that refill request now.
  19.24  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  22.73  bot_turn_ended
  26.39  SENT           Yeah.
  26.40  user           Yeah.
  27.79  bot            Right, I’ll submit that request for review.
  32.53  bot            Your request reference is R Q, one eight six two. It is awaiting prescribing team review.
  34.57  bot_turn_ended
  43.06  user           /session_end
  46.05  bot            Can I help with anything else?
  46.79  bot_turn_ended
```
