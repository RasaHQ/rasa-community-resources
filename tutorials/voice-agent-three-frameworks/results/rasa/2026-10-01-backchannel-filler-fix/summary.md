# rasa: backchannel-filler replay, 2026-10-01-backchannel-filler-fix

- Run: 2026-10-01T15:46:23+00:00 to 2026-10-01T15:47:08+00:00; 1 replays; spend 0.1114 USD (model 0.1071, speech-to-text 0.0043)
- Scenario `backchannel-filler`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Okay.', 'anchor': 'first_bot', 'ends_s_after_anchor': 0.8, 'spoken_s': 0.53}]}
- Server folder: `rasa-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `rasa-backchannel-filler-20261001T154623-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Okay.': False. 'Okay.' sent before the first read-back: False (read-back -5.62 s after it).

```text
   0.10  user           /session_start
   0.11  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   2.55  bot_turn_ended
   8.76  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.77  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
  11.61  bot            Okay, I’ll bring up that refill request now.
  20.38  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  23.83  bot_turn_ended
  26.00  SENT           Okay.
  26.02  user           Okay.
  28.20  bot            Right, I’ll send that request for review.
  34.92  bot            Sorry, I need to read it back once more before sending. Please confirm after the prompt.
  36.86  bot_turn_ended
  36.87  user           /session_end
  40.71  bot            Can I help you with anything else?
  41.52  bot_turn_ended
```
