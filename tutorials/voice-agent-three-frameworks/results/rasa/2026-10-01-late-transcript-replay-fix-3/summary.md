# rasa: late-transcript replay, 2026-10-01-late-transcript-replay-fix-3

- Run: 2026-10-01T15:36:03+00:00 to 2026-10-01T15:37:02+00:00; 1 replays; spend 0.1215 USD (model 0.1153, speech-to-text 0.0062)
- Scenario `late-transcript`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my omeprazole.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `rasa-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-late-transcript-20261001T153603-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: True (read-back 4.75 s after it).

```text
   0.09  user           /session_start
   0.09  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.58  bot_turn_ended
   8.89  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.90  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.98  bot            Okay, I’ll start by checking your details.
  17.10  bot            Thanks Maria, you’re verified. Which medicine do you need a refill request for?
  19.03  bot_turn_ended
  22.84  SENT           Of my omeprazole.
  22.85  user           Of my omeprazole.
  23.67  SENT           Yes, please.
  25.19  bot            Right, I’ll look for that on your record.
  28.42  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  31.85  bot_turn_ended
  31.87  user           Yes, please.
  34.67  bot            Alright, I’ll send that request for review.
  40.71  bot            Sorry, I need to read that back once more before it can be confirmed. Please say yes after the read back is finished.
  43.17  bot_turn_ended
  51.72  user           /session_end
  54.52  bot            Can I help you with anything else?
  55.48  bot_turn_ended
```
