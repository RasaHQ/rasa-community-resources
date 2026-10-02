# rasa: late-transcript replay, 2026-10-01-late-transcript-replay-fix

- Run: 2026-10-01T15:33:55+00:00 to 2026-10-01T15:35:41+00:00; 2 replays; spend 0.2641 USD (model 0.2532, speech-to-text 0.0110)
- Scenario `late-transcript`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my omeprazole.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `rasa-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-late-transcript-20261001T153355-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: True (read-back 3.89 s after it).

```text
   0.12  user           /session_start
   0.13  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.62  bot_turn_ended
   8.85  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.86  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  12.87  bot            Okay, I’ll start the refill request.
  17.94  bot            Thanks, Maria. Which medicine do you need a refill request for?
  19.28  bot_turn_ended
  22.21  SENT           Of my omeprazole.
  22.22  user           Of my omeprazole.
  23.91  SENT           Yes, please.
  25.38  bot            Right, I’ll look for that on your record.
  27.80  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  31.32  bot_turn_ended
  31.34  user           Yes, please.
  33.70  bot            Alright, I’ll submit that request now.
  39.86  bot            Sorry, I could not confirm that just now. Please say again if you would like me to send the omeprazole request to the prescribing team.
  42.43  bot_turn_ended
  51.01  user           /session_end
  54.84  bot            Can I help you with anything else?
  55.61  bot_turn_ended
```

## `rasa-late-transcript-20261001T153355-2`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: True (read-back 1.1 s after it).

```text
   0.12  user           /session_start
   0.12  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   0.13  bot_turn_ended
   6.39  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   6.40  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.69  bot            Okay, I’ll start the refill request now.
  13.61  bot            Thanks Maria. Which medicine do you need a refill request for?
  14.93  bot_turn_ended
  17.72  SENT           Of my omeprazole.
  17.74  user           Of my omeprazole.
  19.17  bot            Right, I’ll look for that on your record.
  19.57  SENT           Yes, please.
  20.66  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  20.68  bot_turn_ended
  20.69  user           Yes, please.
  25.36  bot            Alright, I’ll submit that request for review.
  29.92  bot            I’m sorry, I need to read that back once more before it can be confirmed. Please tell me again if you want this request sent for omeprazole.
  32.55  bot_turn_ended
  40.94  user           /session_end
  44.66  bot            Can I help with anything else?
  45.38  bot_turn_ended
```
