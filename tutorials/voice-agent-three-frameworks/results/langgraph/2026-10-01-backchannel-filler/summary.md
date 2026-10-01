# langgraph: backchannel-filler replay, 2026-10-01-backchannel-filler

- Run: 2026-10-01T15:43:04+00:00 to 2026-10-01T15:43:43+00:00; 1 replays; spend 0.0330 USD (model 0.0287, speech-to-text 0.0043)
- Scenario `backchannel-filler`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Okay.', 'anchor': 'first_bot', 'ends_s_after_anchor': 0.8, 'spoken_s': 0.53}]}
- Server folder: `langgraph`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `langgraph-backchannel-filler-20261001T154304-1`: guard VIOLATED: seq 4: CC-RX-2048 was not selected on a caller turn before the confirmation

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Okay.', 'turn': 1, 'ts': 1790869406.222315}]. Sent on 'Okay.': True. 'Okay.' sent before the first read-back: True (read-back 6.9 s after it).

```text
   2.65  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.65  bot_turn_ended
   8.76  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.76  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
  10.66  bot            One moment while I check your details.
  11.46  SENT           Okay.
  11.46  user           Okay.
  18.36  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  18.36  bot_turn_ended
  22.53  bot            Right, I'll send that request for review.
  24.88  bot            Your request reference is R Q, seven one one eight. It is awaiting prescribing team review.
  24.88  bot_turn_ended
```
