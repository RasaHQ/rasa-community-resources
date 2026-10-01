# strands: wrong-entry-inhaler replay, 2026-10-01-wrong-entry-inhaler

- Run: 2026-10-01T15:48:36+00:00 to 2026-10-01T15:49:06+00:00; 1 replays; spend 0.0442 USD (model 0.0409, speech-to-text 0.0033)
- Scenario `wrong-entry-inhaler`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my inhaler.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `strands`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `strands-wrong-entry-inhaler-20261001T154836-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: False (read-back None s after it).

```text
   0.00  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   1.92  bot_turn_ended
   7.13  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   7.13  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.89  bot            Thanks, one moment while I check.
   9.97  bot            Thanks, Maria. Which medicine do you need a refill request for?
  11.01  bot_turn_ended
  13.79  SENT           Of my inhaler.
  13.79  user           Of my inhaler.
  14.63  bot            Let me find that on your record.
  15.65  SENT           Yes, please.
  15.65  user           Yes, please.
  15.71  bot            I found albuterol inhaler and budesonide inhaler. Which one do you mean?
  16.96  bot_turn_ended
  18.34  bot            I need to know which one before I can request it. Is it albuterol inhaler or budesonide inhaler?
  19.62  bot_turn_ended
```
