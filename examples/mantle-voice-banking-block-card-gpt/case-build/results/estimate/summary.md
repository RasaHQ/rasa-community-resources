# banking-block-card-gpt-voice: run summary

- Case: `banking-block-card`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-29T21:21:43Z to 2026-09-29T21:22:52Z
- Conversations: 1 run, 0 passed, 1 failed
- Caller turns: 3; turn latency p50 2339.3 ms, p95 2553.4 ms, max 2553.4 ms
- LLM calls: 10 (3.33 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 22547 prompt (0 cached), 393 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 3; 
- Case metric unselected_cards_changed: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, browser_audio.handle_message.error 0
- Cost: 0.147176 USD (0.124525 model, 0.022651 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 3 (3 spoken); ended by tracker 3
- End of caller speech to first bot audio with sound, ms: p50 2339.3, p95 2553.4, max 2553.4 (n=3)
- End of caller speech to first bot marker, ms: p50 1866.3, p95 2023.8, max 2023.8 (n=3)
- First end marker per turn, ms: rasa_processing p50 682.4, p95 916.6, max 916.6 (n=3); tts_first_byte p50 474.5, p95 529.6, max 529.6 (n=3); tts_complete p50 1396.6, p95 1723.2, max 1723.2 (n=3)
- Mantle latency_breakdown (3 turns): user_perceived_latency_ms p50 1155.5, p95 1446.2, max 1446.2 (n=3); first_agent_response.llm_time_to_first_token_ms p50 674.7, p95 899.8, max 899.8 (n=3); first_agent_response.llm_total_generation_ms p50 948.2, p95 1239.5, max 1239.5 (n=3)
- Speech-to-text: 2 spoken turns, WER mean 0.0, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 2/2 exact, 2/2 after number normalisation; digits 0/2 exact, 2/2 after number normalisation; card_ending 0/2 exact, 2/2 after number normalisation
- Speech usage: 58.2 s streamed to speech-to-text, 545 characters of bot text (upper bound for text-to-speech); 0.006301 + 0.01635 = 0.022651 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-29
- TTS price: deepgram aura-2-andromeda-en, 0.03 USD per 1,000 characters, from https://deepgram.com/pricing (Aura-2: $0.030/1k characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-other-card-at-confirmation | correction | FAIL | verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→declined, select_card→selected, block_card→awaiting_confirmation | 2553, 2339, 1584 | 0.124525 |

## Failed checks

- `correction-other-card-at-confirmation`: {"type": "tool_called", "tool": "block_card", "args": {"card_ref": "NB-CARD-0102"}, "result": {"status": "succeeded", "reason": "verified_fixture_receipt", "card_ref": "NB-CARD-0102", "unselected_cards_changed": 0, "replacement_ordered": false}} (0 matching call(s), need >= 1)
- `correction-other-card-at-confirmation`: {"type": "tool_order", "steps": [{"tool": "select_card", "result": {"card_ref": "NB-CARD-0101"}}, {"tool": "select_card", "result": {"card_ref": "NB-CARD-0102"}}, {"tool": "block_card", "result": {"status": "succeeded"}}]} (no block_card call after position 6)

Checks read the tracker's tool calls only, never reply wording. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
