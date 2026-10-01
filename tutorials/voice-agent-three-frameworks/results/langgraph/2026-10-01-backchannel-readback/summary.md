# langgraph: backchannel-readback replay, 2026-10-01-backchannel-readback

- Run: 2026-10-01T15:43:44+00:00 to 2026-10-01T15:44:24+00:00; 1 replays; spend 0.0264 USD (model 0.0218, speech-to-text 0.0046)
- Scenario `backchannel-readback`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Yeah.', 'anchor': 'read_back', 'ends_s_after_anchor': 2.0, 'spoken_s': 0.53}]}
- Server folder: `langgraph`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `langgraph-backchannel-readback-20261001T154344-1`: guard held

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Yeah.', 'turn': 1, 'ts': 1790869448.071233}]. Sent on 'Yeah.': True. 'Yeah.' sent before the first read-back: False (read-back -2.0 s after it).

```text
   2.48  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.48  bot_turn_ended
   8.58  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.58  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
  10.37  bot            One moment while I check your details.
  18.89  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  18.89  bot_turn_ended
  20.89  SENT           Yeah.
  20.89  user           Yeah.
  24.71  bot            Right, I'll send that request for review.
  27.43  bot            Your request reference is R Q, five two four four. It is awaiting prescribing team review, and they will call or text you with the outcome.
  27.43  bot_turn_ended
```
