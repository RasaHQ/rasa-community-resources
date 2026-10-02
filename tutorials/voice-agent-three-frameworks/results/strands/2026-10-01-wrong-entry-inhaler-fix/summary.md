# strands: wrong-entry-inhaler replay, 2026-10-01-wrong-entry-inhaler-fix

- Run: 2026-10-01T15:50:41+00:00 to 2026-10-01T15:51:12+00:00; 1 replays; spend 0.0438 USD (model 0.0404, speech-to-text 0.0034)
- Scenario `wrong-entry-inhaler`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my inhaler.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `strands-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `strands-wrong-entry-inhaler-20261001T155041-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: False (read-back None s after it).

```text
   0.00  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.00  bot_turn_ended
   7.18  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   7.18  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.78  bot            Thanks, one moment while I check.
   9.73  bot            Thanks, Maria. Which medicine do you need a refill request for?
  10.78  bot_turn_ended
  13.56  SENT           Of my inhaler.
  13.56  user           Of my inhaler.
  15.18  bot            Let me find that on your record.
  15.41  SENT           Yes, please.
  15.41  user           Yes, please.
  16.54  bot            I found albuterol inhaler and budesonide inhaler. Which one do you mean?
  17.78  bot_turn_ended
  18.94  bot            Which inhaler should I request, albuterol or budesonide?
  20.48  bot_turn_ended
```
