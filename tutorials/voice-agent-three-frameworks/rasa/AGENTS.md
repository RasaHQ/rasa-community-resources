# Rasa Mantle version: Cedar Clinic refill requests by voice

One of three builds of the same agent (see [`../README.md`](../README.md)
and [`../COMPARISON-PLAN.md`](../COMPARISON-PLAN.md)). Cedar Clinic is a
fictional clinic.

Pin: `rasa-pro==3.21.0.dev5`. Model: `gpt-5.5-2026-04-23` through the
`openai` provider, `reasoning_effort: low`. Speech: Speechmatics realtime in,
Speechmatics preview TTS out, through the custom engine classes in
`engines/speechmatics.py`. Channels: `browser_audio` (24 kHz) and
`inspector`.

## Layout and concerns

Every counted file declares its concern in a comment (`concern: <tag>`, or a
`concern-begin:` / `concern-end` region). `tests/test_parity.py` fails on an
untagged file.

| Path | Concern |
|---|---|
| `agent.yml`, `responses.yml`, `skills/default_session_start/skill.md` | agent-logic |
| `skills/request_refill/skill.md` | agent-logic; the `tool_constraints` block is refill-guard |
| `skills/request_refill/tools.py` | agent-logic (bindings to `cedar_clinic`); memory handling and the confirmation record are refill-guard |
| `memory.yml`, `skills/request_refill/memory.yml`, `skills/request_refill/responses.yml` | refill-guard |
| `integrations.yml` | the model group is agent-logic; the channels are voice-loop |
| `engines/` | voice-adapter (Speechmatics as Rasa engines) |
| `pyproject.toml`, `Makefile` | ops |
| `guard.diff` | the refill guard as a diff from the guard-off baseline (not counted) |

## Ground rules

- The domain is `cedar_clinic` in `../shared/clinic`, installed as a path
  dependency and shared with the other two versions. Do not copy it here or
  change its behaviour for one framework.
- Tool descriptions come from `cedar_clinic.tools.TOOL_SPECS`, and the
  persona, rules, greeting and confirmation question from
  `cedar_clinic.instructions`. `tests/test_parity.py` checks both.
- The verified patient id and the selected record entry live in memory only
  tools write (never `llm_settable`). `send_refill_request` keeps its
  `requires` gate and `requires_confirmation`; its body records the
  confirmation with the clinic.
- `engines/speechmatics.py` must keep sending what `cedar_speech` sends:
  `tests/test_speech_parity.py`.
- Barge-in stays off unless a run is labelled as the barge-in variant.
- After a change: `make test`, `make validate`, `make train`. A change to
  skills, tools, the shared parts or the voice settings makes the recorded
  results stale until the spec is rerun (`make spec`, billed).
