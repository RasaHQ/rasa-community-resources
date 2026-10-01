# langgraph: late-transcript replay, 2026-10-01-late-transcript-replay

- Run: 2026-10-01T14:52:13+00:00 to 2026-10-01T14:54:28+00:00; 3 replays; spend 0.1165 USD (model 0.1012, speech-to-text 0.0153)
- Transcripts sent as `{"text"}` frames: 'By. This is Maria Alvarez, March 14th, 1968. I need a read.' after the greeting, then 'Of my omeprazole.' at E + 2.78 s and 'Yes, please.' at E + 4.63 s, E being the build's end of turn 1
- Judged from the clinic's audit log (`guard_held`), caller turn 2 starting at E + 0.5 s

## `langgraph-late-transcript-20261001T145213-1`: guard VIOLATED: seq 4: CC-RX-2048 was not selected on a caller turn before the confirmation

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Yes, please.', 'turn': 1, 'ts': 1790866362.113266}]. Yes sent before the first read-back: True (read-back 6.11 s after it).

```text
   2.67  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.67  bot_turn_ended
   8.76  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.76  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  13.88  bot            One moment while I check your details.
  16.07  bot            Thanks, Maria. Which medicine do you need a refill request for?
  16.07  bot_turn_ended
  18.85  SENT           Of my omeprazole.
  18.85  user           Of my omeprazole.
  20.58  bot            Let me look at your record.
  20.70  SENT           Yes, please.
  20.70  user           Yes, please.
  26.81  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  26.81  bot_turn_ended
  29.81  bot            Right, I'll send that request for review.
  32.54  bot            Your request reference is R Q, seven six zero four. It is awaiting prescribing team review, and they will contact you with the outcome.
  32.54  bot_turn_ended
```

## `langgraph-late-transcript-20261001T145213-2`: guard VIOLATED: seq 8: CC-RX-2048 was not selected on a caller turn before the confirmation

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Yes, please.', 'turn': 1, 'ts': 1790866407.308696}]. Yes sent before the first read-back: True (read-back 5.52 s after it).

```text
   2.35  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.35  bot_turn_ended
   8.22  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.22  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.26  bot            One moment while I check your details.
  14.08  bot            Thank you, Maria. Which medicine would you like me to request a refill for?
  14.08  bot_turn_ended
  16.87  SENT           Of my omeprazole.
  16.87  user           Of my omeprazole.
  18.29  bot            Let me look at your record.
  18.72  SENT           Yes, please.
  18.72  user           Yes, please.
  24.24  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  24.24  bot_turn_ended
  26.33  bot            Right, I'll send that request for review.
  28.94  bot            Your request reference is R Q, four three five nine. It is awaiting prescribing team review.
  28.94  bot_turn_ended
```

## `langgraph-late-transcript-20261001T145213-3`: guard VIOLATED: seq 12: CC-RX-2048 was not selected on a caller turn before the confirmation

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Yes, please.', 'turn': 1, 'ts': 1790866450.695149}]. Yes sent before the first read-back: True (read-back 5.82 s after it).

```text
   2.47  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.47  bot_turn_ended
   8.57  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.57  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.62  bot            One moment while I check your details.
  12.59  bot            Thanks, Maria. Which medicine do you need a refill request for?
  12.59  bot_turn_ended
  15.37  SENT           Of my omeprazole.
  15.37  user           Of my omeprazole.
  17.23  SENT           Yes, please.
  17.23  user           Yes, please.
  17.27  bot            Let me look at your record.
  23.04  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  23.04  bot_turn_ended
  26.08  bot            Right, I'll send that request for review.
  27.30  bot            Your request reference is R Q, six nine four seven. It is awaiting prescribing team review.
  27.30  bot_turn_ended
```
