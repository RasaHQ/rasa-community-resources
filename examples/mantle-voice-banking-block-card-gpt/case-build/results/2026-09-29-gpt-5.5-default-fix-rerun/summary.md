# banking-block-card-gpt-voice: run summary

- Case: `banking-block-card`; channel: browser_audio; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-29T22:01:07Z to 2026-09-29T22:01:47Z
- Conversations: 1 run, 1 passed, 0 failed, 1 skipped for budget
- Caller turns: 1; turn latency p50 2724.9 ms, p95 2724.9 ms, max 2724.9 ms
- LLM calls: 6 (6.0 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 9851 prompt (0 cached), 305 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 1; 
- Case metric unselected_cards_changed: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, voice_channel.audio_missing 0, voice_channel.streaming_task_failed 0, browser_audio.handle_message.error 0
- Cost: 0.069445 USD (0.058405 model, 0.01104 speech); model calls priced by LiteLLM 1.101.2 bundled map

## Voice

- Turns: 1 (1 spoken); ended by tracker 1
- End of caller speech to first bot audio with sound, ms: p50 2724.9, p95 2724.9, max 2724.9 (n=1)
- End of caller speech to first bot marker, ms: p50 2153.3, p95 2153.3, max 2153.3 (n=1)
- First end marker per turn, ms: rasa_processing p50 1143.4, p95 1143.4, max 1143.4 (n=1); tts_first_byte p50 571.7, p95 571.7, max 571.7 (n=1); tts_complete p50 1682.0, p95 1682.0, max 1682.0 (n=1)
- Mantle latency_breakdown (1 turns): user_perceived_latency_ms p50 1715.0, p95 1715.0, max 1715.0 (n=1); first_agent_response.llm_time_to_first_token_ms p50 1091.9, p95 1091.9, max 1091.9 (n=1); first_agent_response.llm_total_generation_ms p50 1457.1, p95 1457.1, max 1457.1 (n=1)
- Speech-to-text: 1 spoken turns, WER mean 0.0, 0 heard nothing, 0 split into more than one user event
- Checked tokens: name 2/2 exact, 2/2 after number normalisation; digits 0/2 exact, 2/2 after number normalisation; card_ending 0/1 exact, 1/1 after number normalisation
- Speech usage: 30.5 s streamed to speech-to-text, 258 characters of bot text (upper bound for text-to-speech); 0.0033 + 0.00774 = 0.01104 USD
- STT price: deepgram flux-general-en, 0.0065 USD per minute, from https://deepgram.com/pricing (Flux English streaming, pay as you go: current $0.0065/min, regular $0.0077/min, promotional) on 2026-09-29
- TTS price: deepgram aura-2-andromeda-en, 0.03 USD per 1,000 characters, from https://deepgram.com/pricing (Aura-2: $0.030/1k characters) on 2026-09-29

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-spouse-card | adversarial | pass | verify_caller→verified | 2725 | 0.058405 |

Checks read the tracker's tool calls only, never reply wording. Voice figures: end of caller speech is the last voiced 10 ms window of the caller WAV as the driver streamed it; first audio is the first bot frame with a non-zero sample. Speech-to-text is billed on every second streamed, silence included.
