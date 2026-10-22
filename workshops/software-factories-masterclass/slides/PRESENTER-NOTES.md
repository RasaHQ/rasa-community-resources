# Presenter notes

Slides 1–4: 10-minute typed teaser. Slides 5–18: 20-minute beginner introduction. Slides 19–26 support the group work; slides 27–29 support sharing.

## 1. A software factory that checks an agent’s changes.

Welcome briefly, then move straight to the teaser. The cover describes the target experience. The supplied package does not yet connect the entire voice factory. State the implemented scope before showing anything. Voice was tested with Deepgram audio files today and failed on the second turn, so type your requests. The microphone path is untested. Rod Rivera, three-hour masterclass.

## 2. Most of today belongs to your group.

Use elapsed time. Explain the two lab blocks and the break. Do not teach every reference chapter on stage. There are 125 minutes for group work and networking.

## 3. “Will I make my meeting?”

Show the real travel demo now. This slide is an illustration, never a screenshot or current travel data. Use a live returned flight or explicitly labeled replay. Change the transfer to two hours. Show what stayed unchanged. The timeline assumes one local date; real implementation must use timezone-aware timestamps.

## 4. See the agent answer, then see it handle a problem.

Finish the 10-minute teaser. If using scripted tool selection or recorded data, say so. A card should show source/freshness, and estimates must not masquerade as airline schedules. Show the factory verdict separately if the end-to-end bridge is unavailable.

## 5. What makes this an AI agent?

1 minute. A language model generates language; the surrounding application supplies instructions, conversation state and tools. Today tool selection is scripted for repeatability. Ask: can fluent wording tell us when a plane lands? No: we need a source.

## 6. A tool brings in information.

1 minute. A function is a named piece of code with inputs and outputs. A tool result can fail or be out of date. The timeline is an estimate using assumptions, not a live road journey prediction.

## 7. Rasa Mantle runs the conversation.

2 minutes. Define framework: reusable software that gives our application its structure. Define skill: a focused set of instructions and tools for a job, here preparing a travel briefing. Mantle does not provide this flight dashboard automatically. Our exercise scripts tool choice; do not imply a live model made every decision.

## 8. Follow one turn through Mantle.

1 minute. Show these stages in the typed teaser. Conversation state means details remembered across turns. If the traveler says no to a suggested flight, the corrected demo lets them choose another. Ask: which stage should report a missing weather source? The tool result and visible answer.

## 9. Deepgram adds a speech interface.

1 minute. Define speech recognition and speech synthesis with the first two examples. Voice is a separate integration to validate. The current workshop does not claim tested end-to-end voice or voice-driven software construction.

## 10. The coding agent has a different job.

1 minute. Ask the room which role needs file-writing permission. Today these are separate exercises. Asking the travel agent to change itself is not a completed workshop capability.

## 11. The OpenAI Agents API runs a builder session.

2 minutes. Session means one managed run of the agent’s work. The optional live builder uses this service; the default workshop builder is repeatable and needs no OpenAI key. Use gpt-6-astra for the documented optional live run; mention cost before starting.

## 12. Agents API and Agents SDK are different.

1 minute. Define protocol as an agreed format for requests and responses. MCP stands for Model Context Protocol. These names describe different responsibilities, not competing names for the same component. Runnable code is in chapter 5; do not begin with an incomplete API snippet.

## 13. What is a software factory?

2 minutes. Candidate or attempt means the proposed files, not the final product. Acceptance test means an executable check of a requirement. The product is the travel application; the factory is the process for changing it. This is our workshop definition, not a claim that the label has a universal standard.

## 14. What makes a factory “dark”?

2 minutes. The term comes from factories able to operate without people on the production floor. Here it describes bounded automation, not the absence of human responsibility. A production system also needs release policy, monitoring and recovery. Today we practice one small local slice.

## 15. Try the rule before the code.

1 minute. Ask participants to predict the first decision before revealing it. This is a teaching example; the supplied chapter 5 task starts with limit 2, and its learner checkpoint asks you to build fresh with 1 or 3.

## 16. The builder cannot grade its own homework.

1 minute. A copied directory is not an operating-system sandbox, so protect execution as well as files. Explain both logical separation and actual execution isolation. Hashes detect mismatches but are not permissions. The existing Python code gate uses macOS sandbox-exec; the fallback checks JSON as data.

## 17. A completed session still needs a decision.

1 minute. Ask for examples of each result. A timed-out API request cannot be labeled REJECT solely because the provider failed. Passing a suite is bounded evidence, not proof of all future behavior.

## 18. Check your understanding with a neighbor.

2 minutes, including answers. Travel agent answers; builder proposes files; independent verifier applies the tests. Builder completion is not acceptance. NOT_READY means the check could not run. People own exception policy. Allow someone to say what remains unclear before forming groups.

## 19. Your group owns one small change.

This begins the ten-minute group briefing. Groups of three or four. An optional observer records evidence and visits another group. Participants use PARTICIPANT-GUIDE.md; stop installing after ten minutes of lab time.

## 20. One guide, two routes.

Be transparent: B does not use the three providers. It keeps people actively learning rather than watching failed installs. A includes separate components; the full bridge remains extension work.

## 21. Lab A: a brief and a first attempt.

Leave this slide up during Lab A. Participants can vary their pace. On A, first run scripted to verify setup, then a live Agents API run when access and budget are ready. On B, run the recovery exercise and design travel cases. Do not interrupt with mini lectures.

## 22. A source label changes what the answer means.

Optional table-side slide. Return to lab work. Do not describe the position-based ETA as a published airline schedule or claim a delay without an authoritative status source.

## 23. Meet another group.

Networking break. Encourage a concrete failure rather than a general product pitch. Example: daylight-saving transition, stale flight observation, ambiguous meeting date, or source outage.

## 24. Lab B: rejection, integration and handoff.

Leave this up for Lab B. The existing integration creates a standalone card, not a new live Mantle release. Groups should label their evidence accurately and identify the missing production step.

## 25. Release exactly the version that passed.

Optional table-side slide. An attempt accepted before integration may fail after integration. The supplied chapter 7 demonstrates local integration and stale-base refusal; it does not implement live deployment.

## 26. Voice has its own acceptance tests.

Explanation only today: Voice was tested with Deepgram audio files today and failed on the second turn, so type your requests. The microphone path is untested. Optional later: check ASR, TTS, timing, interruption and state retention. The version update uses deepgram_flux for Flux ASR and deepgram for Aura-2 TTS. If voice falls back to text, mark voice incomplete.

## 27. Your demo starts with the requirement.

Start closing at minute 165. Take three two-minute demos and use remaining time for discussion. Ask which exact output each group checked. Do not rank groups by number of generated lines or green tests.

## 28. The next step is the complete build-to-voice journey.

Close honestly. Reference BUILD-CONTRACT.md for the remaining implementation and scenarios. A scaffold-based factory is valid, but we must say what the scaffold supplied and what the builder changed.

## 29. One question to take back to work.

Invite one answer. End with a concrete next step: choose one small recurring change in their own system and write independent acceptance examples before building it.
