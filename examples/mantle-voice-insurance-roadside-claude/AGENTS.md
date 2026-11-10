# Rasa Skills project: HarborCover roadside assistance (Claude, browser voice)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`insurance-roadside`. HarborCover and every roadside provider here are
fictional.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `claude-sonnet-5-5` through the
`anthropic` provider (LiteLLM), with a prompt-cache breakpoint on the system
message. Speech: Deepgram Flux (`flux-general-en`) in, Deepgram Aura-2
(`aura-2-andromeda-en`) out. Channels: `browser_audio` (raw WebSocket) and
`inspector`.

## Layout

- `agent.yml`: identity, persona, rules and voice rules (siblings of `agent:`)
- `integrations.yml`: the Claude model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `hooks.py`: the Claude turn-order fix (`lib/turn_order.py`)
- `responses.yml`: the greeting
- `skills/default_session_start/`: greets the caller
- `skills/roadside_dispatch/`: the skill, its tools (`find_policy`,
  `start_dispatch_draft`, `update_dispatch_draft`, `request_dispatch`,
  `request_next_provider`, `check_dispatch`, `route_dispatch_desk`), the
  confirmation question and the pending-draft memory
- `lib/roadside.py`: the roadside desk, the case guard, the tool-sent
  messages and the fictional-organisation allowlist, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard, receipt and turn-order tests
- `case-build/`: scripted calls, the caller-audio manifest, three sample WAVs,
  the caller-audio regeneration script, the case metric and recorded live
  results

## Ground rules

- The guard lives in `lib/roadside.py`, in `request_dispatch` and
  `request_next_provider`, the only functions that send a job to a provider:
  the confirmed place and the provider's suitability are computed there from
  the fixture and the conversation's own events. Never add a tool that
  dispatches without going through them.
- The place comes from the caller's words, never from the policy. The
  registered address is a place only when the caller says the vehicle is
  there, and it is then confirmed at the engine's question like any other.
- The model supplies a policy number and surname, a vehicle reference, a
  service word, the caller's description of the place, a provider name the
  caller asked for, and references copied from tool results. It never
  supplies a fact, a place, a provider's answer or an arrival time.
- The confirmation gate on `request_dispatch` sets no
  `utter_on_user_denial`, so a correction given at the question is answered
  in the same turn. Keep it that way.
- The tools send the caller each outcome themselves through
  `ToolContext.send` (`TOOL_SENDS_RECEIPT`): the assistance reference with
  the provider's answer, a refusal, or the desk reference. The
  `receipt-in-result-only` variant turns it off.
- `lib/roadside.py` refuses fixture data whose insurer is not the casebook
  contract's organisation marked fictional, or whose providers are not on the
  fixture's own list of fictional providers. Keep the fixture fictional and
  keep no list of real names here: the repository lint owns that check.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- Caller WAVs are named from their voice and text and kept out of git except
  the three samples. Changing a caller line in `case-build/conversations.json`
  needs `make caller-audio` (billed Gemini TTS); `make check-caller-audio`
  compares local files with the manifest.
- Do not use OpenAI anywhere in this build (no model, embeddings or caller
  audio): its receipts say none was used.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the calls
  are rerun.
