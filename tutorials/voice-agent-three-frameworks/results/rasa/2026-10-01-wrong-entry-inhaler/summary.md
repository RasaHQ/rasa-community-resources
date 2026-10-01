# rasa: wrong-entry-inhaler replay, 2026-10-01-wrong-entry-inhaler

- Run: 2026-10-01T15:48:41+00:00 to 2026-10-01T15:49:26+00:00; 1 replays; spend 0.0965 USD (model 0.0929, speech-to-text 0.0036)
- Scenario `wrong-entry-inhaler`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my inhaler.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `rasa`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-wrong-entry-inhaler-20261001T154841-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: False (read-back None s after it).

```text
   0.10  user           /session_start
   0.11  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.51  bot_turn_ended
   8.67  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.67  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.64  bot            Okay, I’ll start that refill request now.
  15.99  bot            Thanks, Maria. Which medicine do you need a refill request for?
  17.41  bot_turn_ended
  20.74  SENT           Of my inhaler.
  20.75  user           Of my inhaler.
  22.05  SENT           Yes, please.
  22.96  bot            Right, I’ll check your recorded inhalers.
  27.43  bot            I found albuterol inhaler, two puffs every four to six hours when needed, and budesonide inhaler, one puff twice a day. Which one do you mean?
  30.75  bot_turn_ended
  30.77  user           Yes, please.
  34.61  bot            I need to know which inhaler you mean. Is it albuterol or budesonide?
  36.26  bot_turn_ended
  36.27  user           /session_end
  39.47  bot            Can I help with anything else?
  40.18  bot_turn_ended
```
