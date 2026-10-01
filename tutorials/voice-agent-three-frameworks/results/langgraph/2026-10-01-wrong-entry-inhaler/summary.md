# langgraph: wrong-entry-inhaler replay, 2026-10-01-wrong-entry-inhaler

- Run: 2026-10-01T15:48:36+00:00 to 2026-10-01T15:49:13+00:00; 1 replays; spend 0.0418 USD (model 0.0377, speech-to-text 0.0042)
- Scenario `wrong-entry-inhaler`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my inhaler.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.2}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `langgraph`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `langgraph-wrong-entry-inhaler-20261001T154836-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: False (read-back None s after it).

```text
   2.64  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.64  bot_turn_ended
   8.82  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.82  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  10.80  bot            One moment while I check your details.
  15.53  bot            Thank you, Maria. Which medicine do you need a refill request for?
  15.53  bot_turn_ended
  18.31  SENT           Of my inhaler.
  18.31  user           Of my inhaler.
  19.65  bot            Let me look at your record.
  20.17  SENT           Yes, please.
  20.17  user           Yes, please.
  23.30  bot            I found albuterol inhaler and budesonide inhaler on your record. Which one do you mean?
  23.30  bot_turn_ended
  26.49  bot            Which inhaler do you mean, albuterol or budesonide?
  26.49  bot_turn_ended
```
