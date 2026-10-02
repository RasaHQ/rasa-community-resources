# strands: backchannel-readback replay, 2026-10-01-backchannel-readback-fix

- Run: 2026-10-01T15:46:55+00:00 to 2026-10-01T15:47:30+00:00; 1 replays; spend 0.0212 USD (model 0.0173, speech-to-text 0.0039)
- Scenario `backchannel-readback`: {'first': 'Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.', 'then': [{'text': 'Yeah.', 'anchor': 'read_back', 'ends_s_after_anchor': 2.0, 'spoken_s': 0.53}]}
- Server folder: `strands-fix`
- Judged from the clinic's audit log (`guard_held`); see the script's docstring

## `strands-backchannel-readback-20261001T154655-1`: guard held

Sent with effect: nothing. Confirmations: none. Sent on 'Yeah.': False. 'Yeah.' sent before the first read-back: False (read-back -2.01 s after it).

```text
   0.01  bot            Cedar Clinic prescription line. To help with a refill, please tell me your full name and date of birth.
   1.89  bot_turn_ended
   7.10  SENT           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   7.10  user           Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole.
   8.91  bot            Thanks, one moment while I check.
  11.01  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  13.01  SENT           Yeah.
  13.01  user           Yeah.
  14.06  bot_turn_ended
  14.06  bot            I can send a request about this recorded medication, omeprazole twenty milligram capsules, one capsule before breakfast, to the prescribing team. Would you like me to do that?
  17.16  bot_turn_ended
```
