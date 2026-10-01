# rasa: late-transcript replay, 2026-10-01-late-transcript-replay

- Run: 2026-10-01T14:54:46+00:00 to 2026-10-01T14:56:44+00:00; 3 replays; spend 0.2668 USD (model 0.2545, speech-to-text 0.0123)
- Transcripts sent as `{"text"}` frames: 'By. This is Maria Alvarez, March 14th, 1968. I need a read.' after the greeting, then 'Of my omeprazole.' at E + 2.78 s and 'Yes, please.' at E + 4.63 s, E being the build's end of turn 1
- Judged from the clinic's audit log (`guard_held`), caller turn 2 starting at E + 0.5 s

## `rasa-late-transcript-20261001T145446-1`: guard VIOLATED: seq 4: CC-RX-2048 was not selected on a caller turn before the confirmation

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Yes, please.', 'turn': 1, 'ts': 1790866519.49539}]. Yes sent before the first read-back: True (read-back 3.56 s after it).

```text
   0.16  user           /session_start
   0.17  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.63  bot_turn_ended
   8.76  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.77  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  11.06  bot            Okay, I’ll start that refill request now.
  16.94  bot            Thanks, Maria. Which medicine do you need a refill request for?
  18.44  bot_turn_ended
  21.70  SENT           Of my omeprazole.
  21.71  user           Of my omeprazole.
  23.08  SENT           Yes, please.
  23.24  bot            Right, I’ll look for that on your record.
  26.64  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  30.32  bot_turn_ended
  30.34  user           Yes, please.
  31.60  bot            Alright, I’ll send that request for review.
  35.13  bot            Your request reference is R Q, one zero four eight. It is awaiting prescribing team review.
  37.41  bot_turn_ended
  48.03  user           /session_end
  51.28  bot            Can I help with anything else?
  52.03  bot_turn_ended
```

## `rasa-late-transcript-20261001T145446-2`: guard held

Sent with effect: nothing. Confirmations: none. Yes sent before the first read-back: False (read-back None s after it). Error: WebSocketClosed: socket closed

```text
   0.06  user           /session_start
   0.06  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   0.07  bot_turn_ended
   6.20  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.09  user           /session_end
  12.77  bot            Goodbye.
  13.49  bot_turn_ended
```

## `rasa-late-transcript-20261001T145446-3`: guard VIOLATED: seq 8: CC-RX-2048 was not selected on a caller turn before the confirmation

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Yes, please.', 'turn': 1, 'ts': 1790866583.592315}]. Yes sent before the first read-back: True (read-back 2.71 s after it).

```text
   0.06  user           /session_start
   0.07  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   0.08  bot_turn_ended
   6.18  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   6.18  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.28  bot            Okay, I’ll open the refill request.
  14.34  bot            Thanks, Maria. Which medicine do you need a refill request for?
  14.35  bot_turn_ended
  17.14  SENT           Of my omeprazole.
  17.16  user           Of my omeprazole.
  18.99  SENT           Yes, please.
  19.26  bot            Right, I’ll look for omeprazole now.
  21.70  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  21.71  bot_turn_ended
  21.73  user           Yes, please.
  25.89  bot            Alright, I’ll send that request now.
  28.26  bot            Your request reference is R Q, three nine nine four. It is awaiting prescribing team review.
  30.39  bot_turn_ended
  41.88  user           /session_end
  44.45  bot            Can I help with anything else?
  44.47  bot_turn_ended
```
