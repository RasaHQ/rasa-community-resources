# rasa: wrong-entry-blue replay, 2026-10-01-wrong-entry-blue-fix

- Run: 2026-10-01T15:51:46+00:00 to 2026-10-01T15:52:36+00:00; 1 replays; spend 0.0899 USD (model 0.0850, speech-to-text 0.0049)
- Scenario `wrong-entry-blue`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my blue inhaler.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.6}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `rasa-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-wrong-entry-blue-20261001T155146-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: False (read-back None s after it).

```text
   0.14  user           /session_start
   0.15  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.59  bot_turn_ended
   8.73  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.74  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  11.82  bot            Okay, I’ll start your refill request now.
  17.33  bot            Thanks, Maria. Which medicine do you need a refill request for?
  18.70  bot_turn_ended
  22.00  SENT           Of my blue inhaler.
  22.01  user           Of my blue inhaler.
  23.34  SENT           Yes, please.
  24.28  bot            Right, I’ll look for your blue inhaler.
  26.75  bot            I found albuterol inhaler, and budesonide inhaler. Which one do you mean?
  28.48  bot_turn_ended
  28.50  user           Yes, please.
  30.94  bot            I need to know which one to request. Is it the albuterol inhaler or the budesonide inhaler?
  32.90  bot_turn_ended
  41.43  user           /session_end
  45.94  bot            Can I help you with anything else?
  46.73  bot_turn_ended
```
