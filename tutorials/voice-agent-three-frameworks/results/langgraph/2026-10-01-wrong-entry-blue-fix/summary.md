# langgraph: wrong-entry-blue replay, 2026-10-01-wrong-entry-blue-fix

- Run: 2026-10-01T15:51:20+00:00 to 2026-10-01T15:51:56+00:00; 1 replays; spend 0.0422 USD (model 0.0382, speech-to-text 0.0040)
- Scenario `wrong-entry-blue`: {'first': 'By. This is Maria Alvarez, March 14th, 1968. I need a read.', 'then': [{'text': 'Of my blue inhaler.', 'anchor': 'turn_end', 'ends_s_after_anchor': 2.78, 'spoken_s': 1.6}, {'text': 'Yes, please.', 'anchor': 'turn_end', 'ends_s_after_anchor': 4.63, 'spoken_s': 0.66}]}
- Server folder: `langgraph-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `langgraph-wrong-entry-blue-20261001T155120-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yes, please.': False. 'Yes, please.' sent before the first read-back: False (read-back None s after it).

```text
   2.66  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.66  bot_turn_ended
   8.75  SENT           By. This is Maria Alvarez, March 14th, 1968. I need a read.
   8.75  user           By. This is Maria Alvarez, March 14th, 1968. I need a read.
  11.05  bot            One moment while I check your details.
  13.37  bot            Thank you, Maria. Which medicine do you need a refill request for?
  13.37  bot_turn_ended
  16.16  SENT           Of my blue inhaler.
  16.16  user           Of my blue inhaler.
  17.58  bot            Let me look at your record.
  18.01  SENT           Yes, please.
  18.01  user           Yes, please.
  20.90  bot            I found albuterol inhaler or budesonide inhaler. Which one do you mean?
  20.90  bot_turn_ended
  24.60  bot            I need to know which one you want. Is it albuterol inhaler or budesonide inhaler?
  24.60  bot_turn_ended
```
