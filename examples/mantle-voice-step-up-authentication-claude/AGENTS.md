# Rasa Skills project: Orchard Works step-up authentication (Claude, browser voice)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`step-up-authentication`. Orchard Works is a fictional company.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `claude-sonnet-5-5` through the
`anthropic` provider (LiteLLM). Speech: Deepgram Flux (`flux-general-en`) in,
Deepgram Aura-2 (`aura-2-andromeda-en`) out. Channels: `browser_audio` (raw
WebSocket) and `inspector`.

## Layout

- `agent.yml`: identity, persona, rules and voice rules (siblings of `agent:`)
- `integrations.yml`: the Claude model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `responses.yml`: the greeting
- `skills/default_session_start/`: greets the caller
- `skills/access_reset/`: the skill, its tools (`prepare_access_request`,
  `start_verification`, `check_verification`, `change_access`,
  `cancel_verification`, `route_identity_desk`), the confirmation question and
  the pending-request memory
- `lib/access.py`: the identity service, the case guard and the
  fictional-organisation guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted calls, the caller-audio manifest, three sample WAVs,
  the caller-audio regeneration script, the case metric and recorded live
  results

## Ground rules

- The guard lives in `lib/access.py`, in `change_access`: the subject, the
  challenge and the action are compared there, from the service's own
  records, before anyone's access changes. Never add a tool that changes
  access without going through it.
- The model supplies a spoken name, an action word and references copied from
  tool results. It never supplies a fact or an approval. Nothing the caller
  says (a name, an employee number, a code, a manager's name) verifies them,
  and no tool result may carry a password, a code or a security answer.
- The approval prompt goes only to the subject's registered device. How each
  fixture employee's phone answers is fixture data (`approval`).
- The confirmation gate on `start_verification` sets no
  `utter_on_user_denial`, so a correction given at the question is answered
  in the same turn. Keep it that way.
- `lib/access.py` refuses fixture data whose organisation is not marked
  fictional or is not the organisation the casebook contract names. Keep the
  fixture fictional and keep no list of real names here: the repository lint
  owns that check.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- Caller WAVs are named from their voice and text and kept out of git except
  the three samples. Changing a caller line in `case-build/conversations.json`
  needs `make caller-audio` (billed Gemini TTS); `make check-caller-audio`
  compares local files with the manifest.
- Do not use OpenAI anywhere in this build (no model, embeddings or caller
  audio): the build was made without OpenAI credit, and its receipts say so.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the calls
  are rerun.
