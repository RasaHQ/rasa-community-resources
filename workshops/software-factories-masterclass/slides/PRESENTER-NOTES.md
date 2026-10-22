# Presenter notes

Arrow keys advance the deck. N toggles notes. The deck works offline. Slides 20, 23 and 24 are optional table-side explanations. Main teaching ends with the group briefing at minute 40.

## 1. A software factory that checks an agent’s changes.

Welcome briefly, then move straight to the teaser. The cover describes the target experience. The supplied package does not yet connect the entire voice factory. State the implemented scope before showing anything. Voice was tested with Deepgram audio files today and failed on the second turn, so type your requests. The microphone path is untested. Rod Rivera, three-hour masterclass.

## 2. “Will I make my meeting?”

Show the real travel demo now. This slide is an illustration, never a screenshot or current travel data. Use a live returned flight or explicitly labeled replay. Change the transfer to two hours. Show what stayed unchanged. The timeline assumes one local date; real implementation must use timezone-aware timestamps.

## 3. The screen makes the answer inspectable.

Finish the 10-minute teaser. If using scripted tool selection or recorded data, say so. A card should show source/freshness, and estimates must not masquerade as airline schedules. Show the factory verdict separately if the end-to-end bridge is unavailable.

## 4. Most of today belongs to your group.

Use elapsed time. Explain the two lab blocks and the break. Do not teach every reference chapter on stage. There are 125 minutes for group work and networking.

## 5. A software factory turns a request into a checked change.

Assume nobody has heard the term. A factory here isn’t a building. It is a fixed routine that every change goes through. The point is trust: coding agents often report success when the change is wrong, and nobody can read every line they write. The factory replaces reading with checking.

## 6. A dark factory runs with the lights off.

Lights-out manufacturing is the image. Stress that dark doesn’t mean unsupervised: people decide what good looks like and own the exceptions. Today you build a small version of this: request, builder, protected checks, decision.

## 7. Rasa Mantle is how we build the travel agent.

Introduce Mantle as the product people talk to. A Mantle agent is a folder of files: agent.yml, skills and tool connections. In today's exercises the choice of tool is scripted so results repeat; the flight, weather and rate data are real or a labeled recording. Chapter 1 of the book opens the folder and shows each part.

## 8. The OpenAI Agents API runs a coding agent for us.

This is the OpenAI Agents API, a hosted service, and a different thing from the OpenAI Agents SDK, a separate Python library. Our code reaches the service through OpenAI's normal Python client. Running it costs money, so today you see a recording of a paid build and a scripted builder that makes no model calls. Chapter 5 shows how to run it yourself.

## 9. Two agents have different jobs.

This distinction is essential. The existing travel specialist choosing source tools is not the coding builder. Identify the missing bridge explicitly. Ask the room: which agent needs permission to change files?

## 10. Each part has a clear responsibility.

Spend two minutes here. Mantle is the orchestrator in Rasa; the Agents API is a managed service, not another local library. Deepgram is the speech provider. Neither provider automatically supplies this dashboard.

## 11. The Agents API runs the builder session.

Use official Agents API terminology. Explain that the openai Python client can expose beta.agents without importing Agent or Runner from the Agents SDK. Complete code is in the chapter 5 driver via zeocore. Do not run this abbreviated snippet.

## 12. MCP is the connection to your application.

This slide is the target factory connection. The shipped travel service already exposes source tools over MCP, but it does not expose submit_build/get_build/cancel_build. Those are proposed application tools in BUILD-CONTRACT.md. Long builds should return a job ID quickly.

## 13. A brief becomes a testable request.

Give the group a concrete feature from the existing code. Public requirements and public tests are useful to the builder. Protect the evaluator from writes; hiding every test is not the defining idea.

## 14. The builder cannot grade its own homework.

A copied directory is not an operating-system sandbox, so protect execution as well as files. Explain both logical separation and actual execution isolation. Hashes detect mismatches but are not permissions. The existing Python code gate uses macOS sandbox-exec; the fallback checks JSON as data.

## 15. A completed session still needs a decision.

Ask for examples of each result. A timed-out API request cannot be labeled REJECT solely because the provider failed. Passing a suite is bounded evidence, not proof of all future behavior.

## 16. Dark factories need an explicit release policy.

Define dark factory as reducing routine manual intervention within a bounded workflow. Tests are not the only possible control; policies, human escalation, monitoring and rollback matter. The workshop is an introduction, not proof of unattended production readiness.

## 17. Your group owns one small change.

This begins the ten-minute group briefing. Groups of three or four. An optional observer records evidence and visits another group. Participants use PARTICIPANT-GUIDE.md; stop installing after ten minutes of lab time.

## 18. One guide, two routes.

Be transparent: B does not use the three providers. It keeps people actively learning rather than watching failed installs. A includes separate components; the full bridge remains extension work.

## 19. Lab A: a brief and a first attempt.

Leave this slide up during Lab A. Participants can vary their pace. On A, first run scripted to verify setup, then a live Agents API run when access and budget are ready. On B, run the recovery exercise and design travel cases. Do not interrupt with mini lectures.

## 20. A source label changes what the answer means.

Optional table-side slide. Return to lab work. Do not describe the position-based ETA as a published airline schedule or claim a delay without an authoritative status source.

## 21. Meet another group.

Networking break. Encourage a concrete failure rather than a general product pitch. Example: daylight-saving transition, stale flight observation, ambiguous meeting date, or source outage.

## 22. Lab B: rejection, integration and handoff.

Leave this up for Lab B. The existing integration creates a standalone card, not a new live Mantle release. Groups should label their evidence accurately and identify the missing production step.

## 23. Release the exact artifact that passed.

Optional table-side slide. An attempt accepted before integration may fail after integration. The supplied chapter 7 demonstrates local integration and stale-base refusal; it does not implement live deployment.

## 24. Voice has its own acceptance tests.

Explanation only today: Voice was tested with Deepgram audio files today and failed on the second turn, so type your requests. The microphone path is untested. Optional later: check ASR, TTS, timing, interruption and state retention. The version update uses deepgram_flux for Flux ASR and deepgram for Aura-2 TTS. If voice falls back to text, mark voice incomplete.

## 25. Your demo starts with the requirement.

Start closing at minute 165. Take three two-minute demos and use remaining time for discussion. Ask which exact output each group checked. Do not rank groups by number of generated lines or green tests.

## 26. The next step is the complete build-to-voice journey.

Close honestly. Reference BUILD-CONTRACT.md for the remaining implementation and scenarios. A scaffold-based factory is valid, but we must say what the scaffold supplied and what the builder changed.

## 27. One question to take back to work.

Invite one answer. End with a concrete next step: choose one small recurring change in their own system and write independent acceptance examples before building it.

