# banking-block-card-gpt-voice: run summary

- Case: `banking-block-card`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-29T22:01:55Z to 2026-09-29T22:03:04Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 3; turn latency p50 1954.4 ms, p95 3009.6 ms, max 3009.6 ms
- LLM calls: 11 (3.67 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 24818 prompt (3328 cached), 418 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 3; 
- Case metric unselected_cards_changed: 0 over 1 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, browser_audio.handle_message.error 0
- Cost: 0.145201 USD (0.121654 model, 0.023547 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 3 (3 spoken); ended by tracker 3
- End of caller speech to first bot audio with sound, ms: p50 1954.4, p95 3009.6, max 3009.6 (n=3)
- End of caller speech to first bot marker, ms: p50 1378.5, p95 2390.3, max 2390.3 (n=3)
- First end marker per turn, ms: rasa_processing p50 701.1, p95 857.0, max 857.0 (n=3); tts_first_byte p50 437.3, p95 575.9, max 575.9 (n=3); tts_complete p50 1400.8, p95 1486.0, max 1486.0 (n=3)
- Mantle latency_breakdown (3 turns): user_perceived_latency_ms p50 1276.9, p95 1294.3, max 1294.3 (n=3); first_agent_response.llm_time_to_first_token_ms p50 671.3, p95 827.6, max 827.6 (n=3); first_agent_response.llm_total_generation_ms p50 1094.6, p95 1099.5, max 1099.5 (n=3)
- Speech-to-text: 3 spoken turns, WER mean 0.0, 0 heard nothing, 0 split into more than one user event
- Checked tokens: digits 0/3 exact, 3/3 after number normalisation; card_ending 0/1 exact, 1/1 after number normalisation
- Speech usage: 60.1 s streamed to speech-to-text, 568 characters of bot text (upper bound for text-to-speech); 0.006507 + 0.01704 = 0.023547 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-29
- TTS price: deepgram aura-2-andromeda-en, 0.03 USD per 1,000 characters, from https://deepgram.com/pricing (Aura-2: $0.030/1k characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-verification-retry | recovery | pass | verify_caller→not_verified/identity_mismatch, verify_caller→verified, select_card→selected, block_card→awaiting_confirmation, block_card→succeeded/verified_fixture_receipt | 3010, 1954, 1439 | 0.121654 |

Checks read the tracker's tool calls only, never reply wording. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
