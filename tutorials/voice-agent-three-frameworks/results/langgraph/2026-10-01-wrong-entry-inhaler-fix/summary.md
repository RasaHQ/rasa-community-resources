# langgraph: wrong-entry-inhaler replay, 2026-10-01-wrong-entry-inhaler-fix

- Run: 2026-10-01T15:50:41+00:00 to 2026-10-01T15:51:19+00:00; 1 replays; spend 0.0428 USD (model 0.0385, speech-to-text 0.0042)
- Scenario `wrong-entry-inhaler`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my inhaler.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `langgraph-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `langgraph-wrong-entry-inhaler-20261001T155041-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: False (read-back None s after it).

```text
   2.61  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.61  bot_turn_ended
   8.48  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.48  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.68  bot            One moment while I check your details.
  13.61  bot            Thank you, Maria. Which medicine do you need a refill request for?
  13.61  bot_turn_ended
  16.40  SENT           Of my inhaler.
  16.40  user           Of my inhaler.
  17.81  bot            Let me look at your record.
  18.25  SENT           Yes, please.
  18.25  user           Yes, please.
  22.68  bot            I found albuterol inhaler, two puffs every four to six hours when needed, and budesonide inhaler, one puff twice a day. Which one do you mean?
  22.68  bot_turn_ended
  26.08  bot            Which one should I request, albuterol inhaler or budesonide inhaler?
  26.08  bot_turn_ended
```
