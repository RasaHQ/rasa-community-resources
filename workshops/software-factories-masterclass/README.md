# A software factory that checks an agent’s changes

Three-hour workshop with Rod Rivera. Rasa Mantle, Deepgram and the OpenAI Agents API.
Updated 22 October 2026.

**Start with [PARTICIPANT-GUIDE.md](PARTICIPANT-GUIDE.md).** Open `slides/index.html` for the revised presentation. The facilitator uses `RUN-SHEET.md` and `slides/PRESENTER-NOTES.md`.

The target experience is a spoken product request, a builder session, independent acceptance checks, and a released flight assistant with voice and visual cards. This package contains a travel assistant scaffold and a separate factory exercise. **The automatic connection from spoken build request to a newly launched assistant remains unfinished.** The audit identifies the missing components and gives exact acceptance criteria. Do not present the separate demonstrations as a completed end-to-end factory.

## What changed

- One three-hour schedule: 10-minute teaser, 20-minute concepts, 10-minute group briefing, 55-minute lab, 15-minute networking break, 55-minute lab, 15-minute demos.
- A participant route with checkpoints, expected results, recovery instructions and a path for participants without macOS.
- The travel scaffold now targets Rasa Pro **3.21.0**. Its model group is selected in `agent.yml`; Flux recognition uses `deepgram_flux`. Its dependency lock is regenerated.
- The Agents API and Agents SDK are clearly distinguished. Python's `openai` client can call the Agents API; that does not make it the `openai-agents` framework.
- Revised slides use Rasa's supplied palette, official logo and open fallback fonts, with concrete travel examples and architecture diagrams.

## What is demonstrated

The teaser uses typed requests. Tool selection is scripted. Sources are either explicitly labeled REPLAY or current public sources. Voice has not been tested end to end. The live Agents API builder is an optional paid extension, with the default model **gpt-6-astra**. The `openai-agents` SDK appendix is not the API implementation used here.

The built card is not automatically installed in the running travel demo. A complete voice-triggered build and release remains extension work. [BUILD-CONTRACT.md](BUILD-CONTRACT.md) defines that work without claiming it exists.

Track B: **Python 3.12 only (3.13 and 3.14 stop with NOT_READY). Windows untested.** It teaches the factory method without provider accounts.

The standalone example is in `examples/mantle-flight-briefing-openai-agents/` in this repository. Its [self-paced guide](../../examples/mantle-flight-briefing-openai-agents/SELF-PACED-GUIDE.md) explains which paths use live providers.

## Where to go

| File | Purpose |
|---|---|
| [PARTICIPANT-GUIDE.md](PARTICIPANT-GUIDE.md) | Self-paced route and checkpoints |
| [TECHNICAL-AUDIT.md](TECHNICAL-AUDIT.md) | Findings, corrections, evidence and unresolved demo blockers |
| [BUILD-CONTRACT.md](BUILD-CONTRACT.md) | The voice factory's required interfaces and acceptance scenarios |
| [RUN-SHEET.md](RUN-SHEET.md) | The single timing authority for the event |
| [PREWORK.md](PREWORK.md) | Setup and accounts |
| `book/ready/ch00/demo/` | Updated travel assistant scaffold |
| `book/ready/ch05/` | Separate Agents API builder exercise, macOS gates |
| `book/ready/ch06/`, `ch07/` | Rejection and integration exercises |
| `book/ready/ch08/` | Data-only factory/recovery exercise, Python 3.12 |
| `factory/`, `openai-mcp/`, `brief-me-before-i-fly/` | Historical extensions with their own older pins |
| `archive/2026-10-22-original/` | Superseded teaching plans and original slide source |

The latest documented tagged Mantle release and PyPI release were both 3.21.0 when checked. “Unreleased” documentation is not part of that release. Live voice, API account access, source availability, and the complete release journey still need rehearsal with your credentials. See the audit for exactly what was run.
