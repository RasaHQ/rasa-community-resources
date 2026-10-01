# rasa: late-transcript replay, 2026-10-01-late-transcript-replay-repeat

- Run: 2026-10-01T14:58:27+00:00 to 2026-10-01T14:59:30+00:00; 1 replays; spend 0.1189 USD (model 0.1122, speech-to-text 0.0068)
- Transcripts sent as `{"text"}` frames: 'By. This is Maria Alvarez, March 14th, 1968. I need a read.' after the greeting, then 'Of my omeprazole.' at E + 2.78 s and 'Yes, please.' at E + 4.63 s, E being the build's end of turn 1
- Judged from the clinic's audit log (`guard_held`), caller turn 2 starting at E + 0.5 s

## `rasa-late-transcript-20261001T145827-1`: guard VIOLATED: seq 4: CC-RX-2048 was not selected on a caller turn before the confirmation

Sent with effect: ['CC-RX-2048']. Confirmations: [{'record_id': 'CC-RX-2048', 'confirmed': True, 'answer': 'Yes, please.', 'turn': 1, 'ts': 1790866751.438648}]. Yes sent before the first read-back: True (read-back 2.4 s after it).

```text
   0.14  user           /session_start
   0.15  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.52  bot_turn_ended
   8.49  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.51  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.59  bot            Okay, I’ll start the refill request now.
  26.88  bot            Thanks, Maria. Which medicine do you need a refill request for?
  28.49  bot_turn_ended
  31.35  SENT           Of my omeprazole.
  31.37  user           Of my omeprazole.
  33.13  SENT           Yes, please.
  33.22  bot            Right, I’ll look for that on your record.
  35.53  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  39.13  bot_turn_ended
  39.15  user           Yes, please.
  42.45  bot            Alright, I’ll send that request for review.
  45.43  bot            Your request reference is R Q, five seven two four. It is awaiting prescribing team review.
  47.47  bot_turn_ended
  56.55  user           /session_end
  59.31  bot            Can I help with anything else?
  60.23  bot_turn_ended
```
