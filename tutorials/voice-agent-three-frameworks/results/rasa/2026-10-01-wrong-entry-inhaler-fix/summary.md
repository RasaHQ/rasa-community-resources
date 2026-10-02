# rasa: wrong-entry-inhaler replay, 2026-10-01-wrong-entry-inhaler-fix

- Run: 2026-10-01T15:50:45+00:00 to 2026-10-01T15:51:40+00:00; 1 replays; spend 0.0948 USD (model 0.0893, speech-to-text 0.0055)
- Scenario `wrong-entry-inhaler`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my inhaler.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `rasa-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-wrong-entry-inhaler-20261001T155045-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: False (read-back None s after it).

```text
   0.08  user           /session_start
   0.08  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.55  bot_turn_ended
   8.58  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.59  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  11.19  bot            Okay, I’ll start that refill request now.
  18.20  bot            Thanks, Maria. Which medicine do you need a refill request for?
  19.55  bot_turn_ended
  22.34  SENT           Of my inhaler.
  22.36  user           Of my inhaler.
  24.18  SENT           Yes, please.
  24.87  bot            Right, I’ll look for your inhaler now.
  28.68  bot            I found albuterol inhaler, two puffs every four to six hours when needed, and budesonide inhaler, one puff twice a day. Which one do you mean?
  31.88  bot_turn_ended
  31.90  user           Yes, please.
  35.16  bot            I need to know which inhaler you mean. Please say albuterol or budesonide.
  37.06  bot_turn_ended
  45.85  user           /session_end
  49.18  bot            Can I help with anything else?
  49.92  bot_turn_ended
```
