# LangGraph version: Cedar Clinic refill requests by voice

One of three builds of the same agent (see [`../README.md`](../README.md)
and [`../COMPARISON-PLAN.md`](../COMPARISON-PLAN.md)). Cedar Clinic is a
fictional clinic.

Pins: `langgraph==1.2.12`, `langchain==1.4.3`, `langchain-openai==1.6.7`.
Model: `gpt-5.5-2026-04-23` through `ChatOpenAI` with
`reasoning_effort="low"` and `use_responses_api=True`. Speech: Speechmatics
realtime in, Speechmatics preview TTS out, through `../shared/speech`.

## Layout and concerns

Every counted file declares its concern in a comment (`concern: <tag>`, or a
`concern-begin:` / `concern-end` region). `tests/test_parity.py` fails on an
untagged file.

| Path | Concern |
|---|---|
| `agent.py` | agent-logic (model, prompt, tool bindings, `create_agent`); the tools' state updates and the middleware wiring are refill-guard |
| `guard.py` | refill-guard (private state, `RefillGuard` middleware, `interrupt()`, the yes/no classifier) |
| `voice_loop.py` | voice-loop; the resume of a paused confirmation and the speaking of the guard's lines are refill-guard |
| `server.py` | voice-loop (Starlette routes) |
| `pyproject.toml`, `Makefile` | ops |
| `guard.diff` | the refill guard as a diff from the guard-off baseline (not counted) |

## Ground rules

- The domain is `cedar_clinic` in `../shared/clinic` and the speech clients
  are `cedar_speech` in `../shared/speech`, both path dependencies. Do not
  copy or change them for one framework.
- Tool names, descriptions and parameters come from
  `cedar_clinic.tools.TOOL_SPECS`; the system prompt is
  `cedar_clinic.instructions.system_prompt()` verbatim. `tests/test_parity.py`
  checks both.
- The patient id and the selected entry live in `RefillState`, private graph
  state that only tools write through `Command` updates. No tool takes a
  patient id from the model.
- `send_refill_request` stays hidden until a medicine is selected, is refused
  unless its record id is the selected one, and runs only after
  `interrupt()` is resumed with a yes from a later caller turn.
- Barge-in stays off (`voice_loop.INTERRUPTIONS_ENABLED`) unless a run is
  labelled as the barge-in variant.
- After a change: `make test`. A change to the agent, the guard, the voice
  loop or the shared parts makes the recorded results stale until the spec is
  rerun (`make spec`, billed).
