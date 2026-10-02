# langgraph: late-transcript replay, 2026-10-01-late-transcript-replay-fix

- Run: 2026-10-01T15:35:58+00:00 to 2026-10-01T15:38:18+00:00; 3 replays; spend 0.0948 USD (model 0.0789, speech-to-text 0.0159)
- Scenario `late-transcript`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my omeprazole.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `langgraph-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `langgraph-late-transcript-20261001T153558-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: True (read-back 6.32 s after it).

```text
   2.66  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.66  bot_turn_ended
   8.84  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.84  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  11.30  bot            One moment while I check your details.
  13.68  bot            Thanks, Maria. Which medicine do you need a refill request for?
  13.68  bot_turn_ended
  16.46  SENT           Of my omeprazole.
  16.46  user           Of my omeprazole.
  17.85  bot            Let me look at your record.
  18.32  SENT           Yes, please.
  18.32  user           Yes, please.
  24.63  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  24.63  bot_turn_ended
  28.11  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  28.11  bot_turn_ended
```

## `langgraph-late-transcript-20261001T153558-2`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: True (read-back 7.28 s after it).

```text
   2.65  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.65  bot_turn_ended
   8.79  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.79  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.90  bot            One moment while I check your details.
  14.99  bot            Thanks, Maria. Which medicine do you need a refill request for?
  14.99  bot_turn_ended
  17.77  SENT           Of my omeprazole.
  17.77  user           Of my omeprazole.
  19.28  bot            Let me look at your record.
  19.62  SENT           Yes, please.
  19.62  user           Yes, please.
  26.90  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  26.90  bot_turn_ended
  30.49  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  30.49  bot_turn_ended
```

## `langgraph-late-transcript-20261001T153558-3`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: True (read-back 5.76 s after it).

```text
   2.53  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.53  bot_turn_ended
   8.73  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.73  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.77  bot            One moment while I check your details.
  13.96  bot            Thanks, Maria, you are verified. Which medicine do you need a refill request for?
  13.96  bot_turn_ended
  16.75  SENT           Of my omeprazole.
  16.75  user           Of my omeprazole.
  18.10  bot            Let me look at your record.
  18.60  SENT           Yes, please.
  18.60  user           Yes, please.
  24.36  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  24.36  bot_turn_ended
  27.80  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  27.80  bot_turn_ended
```
