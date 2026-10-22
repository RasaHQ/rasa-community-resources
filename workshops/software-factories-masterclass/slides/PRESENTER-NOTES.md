# Presenter notes

Arrow keys advance the deck. N toggles notes. The deck works offline. Slides 16, 19 and 20 are optional table-side explanations. Main teaching ends with the group briefing at minute 40.

## 1. A voice agent that builds a voice agent.

Welcome briefly, then move straight to the teaser. The cover describes the target experience. The supplied package does not yet connect the entire voice factory. State the implemented scope before showing anything. Rod Rivera, three-hour masterclass.

## 2. “Will I make my meeting?”

Show the real travel demo now. This slide is an illustration, never a screenshot or current travel data. Use a live returned flight or explicitly labelled replay. Change the transfer to two hours. Show what stayed unchanged. The timeline assumes one local date; real implementation must use timezone-aware timestamps.

## 3. The screen makes the answer inspectable.

Finish the 10-minute teaser. If using scripted tool selection or recorded data, say so. A card should show source/freshness, and estimates must not masquerade as airline schedules. Show the factory verdict separately if the end-to-end bridge is unavailable.

## 4. Most of today belongs to your group.

Use elapsed time. Explain the two lab blocks and the break. Do not teach every reference chapter on stage. There are 125 minutes for group work and networking.

## 5. Two agents have different jobs.

This distinction is essential. The existing travel specialist choosing source tools is not the coding builder. Identify the missing bridge explicitly. Ask the room: which agent needs permission to change files?

## 6. Each part has a clear responsibility.

Spend two minutes here. Mantle is the orchestrator in Rasa; the Agents API is a managed service, not another local library. Deepgram is the speech provider. Neither provider automatically supplies this dashboard.

## 7. The Agents API runs the builder session.

Use official Agents API terminology. Explain that the openai Python client can expose beta.agents without importing Agent or Runner from the Agents SDK. Complete code is in the chapter 5 driver via zeocore. Do not run this abbreviated snippet.

## 8. MCP is the connection to your application.

This slide is the target factory connection. The shipped travel service already exposes source tools over MCP, but it does not expose submit_build/get_build/cancel_build. Those are proposed application tools in BUILD-CONTRACT.md. Long builds should return a job ID quickly.

## 9. A brief becomes a testable request.

Give the group a concrete feature from the existing code. Public requirements and public tests are useful to the builder. Protect the evaluator from writes; hiding every test is not the defining idea.

## 10. The builder cannot grade its own homework.

Explain both logical separation and actual execution isolation. Hashes detect mismatches but are not permissions. The existing Python code gate uses macOS sandbox-exec; the fallback checks JSON as data.

## 11. A completed session still needs a decision.

Ask for examples of each result. A timed-out API request cannot be labelled REJECT solely because the provider failed. Passing a suite is bounded evidence, not proof of all future behavior.

## 12. Dark factories need an explicit release policy.

Define dark factory as reducing routine manual intervention within a bounded workflow. Tests are not the only possible control; policies, human escalation, monitoring and rollback matter. The workshop is an introduction, not proof of unattended production readiness.

## 13. Your group owns one small change.

This begins the ten-minute group briefing. Groups of three or four. An optional observer records evidence and visits another group. Participants use PARTICIPANT-GUIDE.md; stop installing after ten minutes of lab time.

## 14. One guide, two routes.

Be transparent: B does not use the three providers. It keeps people actively learning rather than watching failed installs. A includes separate components; the full bridge remains extension work.

## 15. Lab A: a brief and a first candidate.

Leave this slide up during Lab A. Participants can vary their pace. On A, first run scripted to verify setup, then a live Agents API run when access and budget are ready. On B, run the recovery exercise and design travel cases. Do not interrupt with mini lectures.

## 16. A source label changes what the answer means.

Optional table-side slide. Return to lab work. Do not describe the position-based ETA as a published airline schedule or claim a delay without an authoritative status source.

## 17. Meet another group.

Networking break. Encourage a concrete failure rather than a general product pitch. Example: daylight-saving transition, stale flight observation, ambiguous meeting date, or source outage.

## 18. Lab B: rejection, integration and handoff.

Leave this up for Lab B. The existing integration creates a standalone card, not a new live Mantle release. Groups should label their evidence accurately and identify the missing production step.

## 19. Release the exact artifact that passed.

Optional table-side slide. A candidate accepted before integration may fail after integration. The supplied chapter 7 demonstrates local integration and stale-base refusal; it does not implement live deployment.

## 20. Voice has its own acceptance tests.

Optional. Check ASR, TTS, timing, interruption and state retention. The version update uses deepgram_flux for Flux ASR and deepgram for Aura-2 TTS. If voice falls back to text, mark voice incomplete.

## 21. Your demo starts with the requirement.

Start closing at minute 165. Take three two-minute demos and use remaining time for discussion. Ask which exact output each group checked. Do not rank groups by number of generated lines or green tests.

## 22. The next step is the complete build-to-voice journey.

Close honestly. Reference BUILD-CONTRACT.md for the remaining implementation and scenarios. A scaffold-based factory is valid, but we must say what the scaffold supplied and what the builder changed.

## 23. One question to take back to work.

Invite one answer. End with a concrete next step: choose one small recurring change in their own system and write independent acceptance examples before building it.

