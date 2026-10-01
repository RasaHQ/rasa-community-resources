# rasa: backchannel-filler replay, 2026-10-01-backchannel-filler

- Run: 2026-10-01T15:43:11+00:00 to 2026-10-01T15:43:57+00:00; 1 replays; spend 0.1123 USD (model 0.1078, speech-to-text 0.0045)
- Scenario `backchannel-filler`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Okay.', 'anchor': 'first_bot', 'ends_s_after_anchor': 0.8, 'spoken_s': 0.53}]}
- Server folder: `rasa`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-backchannel-filler-20261001T154311-1`: guard held

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Okay.', 'turn': 1, 'ts': 1790869424.480323}]. Sent on 'Okay.': True. 'Okay.' sent before the first read-back: False (read-back -8.26 s after it).

```text
   0.09  user           /session_start
   0.10  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.57  bot_turn_ended
   8.74  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.75  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
  12.10  bot            Okay, I’ll look up your record now.
  21.17  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  24.71  bot_turn_ended
  29.43  SENT           Okay.
  29.44  user           Okay.
  31.72  bot            Right, I’ll send that request for review.
  35.52  bot            Your request reference is R Q, seven four nine two. It is awaiting prescribing team review.
  37.79  bot_turn_ended
  37.80  user           /session_end
  40.62  bot            Can I help with anything else?
  41.39  bot_turn_ended
```
