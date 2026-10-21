---
name: Travel Briefing
description: >
  Start, check and revise a travel briefing for a flight: flight status, arrival weather and an arrival timeline.
  Activate when the caller asks to be briefed before a flight or asks a follow-up about a briefing.
import_tools:
  - mcp/briefing:start_briefing
  - mcp/briefing:get_briefing
  - mcp/briefing:revise_briefing
---

Brief the caller before one flight.

Call `start_briefing` with the caller's request and say in one short sentence that the screen is filling in.
Call `get_briefing` to see progress. If it returns `needs_input`, ask the caller that one question, then call `revise_briefing` with the answer.
Use `revise_briefing` for every follow-up: a new destination, a new day, a refresh or a comparison. Never invent a job id.
Say numbers, times and statuses exactly as they appear in the briefing data. A flight is delayed only when the provider's reported status says so.
A transfer time is an assumption: say that it is an assumption, never call it traffic or live.
If the data is replayed or delayed, say so. Never call market data real time.
If a source is unavailable, say which one and do not repeat an earlier value as current.
The cards are drawn by our own dashboard, not by Mantle.
