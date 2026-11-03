# Teach the travel factory

Open the projector PDF and the learner README. For an interactive presentation, open the built slides/index.html in a browser; arrows navigate and N reveals the speaking cue. Each slide names the elapsed time. Open the teaching notes in slides/PRESENTER-NOTES.md beside the PDF.

**Opening eight minutes.** Begin with the two calls participants will make. Ask why a current forecast cannot answer the landing question. Then introduce the developer’s change request: when two flight records match, ask which one the traveler means. Use that request to explain the factory, identify each technology’s job, and walk through the agenda. Invite learners to open the README and launch their Codespace during the introduction.

| At minute | Ask a learner to show | If the live route is blocked |
| --- | --- | --- |
| 15 | The airport forecast hour and rate reference date | Try the other public endpoint. Work through the labeled FX fixture in tests/test_travel.py while waiting. |
| 30 | Two tool events in the starter’s Inspector | Record live provider results and mark conversation pending. |
| 75 | A four-tool project built from a reviewed Codex spec | Use the labeled sample; distinguish it from a Codex generation. |
| 105 | The tool confirmation in the factory agent, and what happens on denial | Walk the request through studio/skills/build_agent and the builder source. |
| 135 | A hosted artifact receipt and a separately running traveler project | Use a sample candidate through approval; list hosted generation as pending. |
| 165 | Which local evening was searched, which arrival time drove the forecast and which date drove FX | Use the deterministic timezone and missing-provider tests. |
| 180 | A reproducible build note and one home exercise | Keep the output folder and stop the Codespace. |

The supported airports for this edition are OSL, BGO, JFK, LHR, CDG, MAD and MEX (flight tools cover only Oslo–Bergen in either direction). Codespaces costs, provider quotas, Codex calls and hosted Agents sessions belong to the accounts used. Have workshop access ready. Jobs can take longer than scheduled; shorten discussion or move the second generation to home practice. Keep the first live-data exercise and the exercise that runs a generated Mantle product.

**Sample grading question.** A learner offers “there are no flights” when the provider cannot be reached. Ask them to show the `state` field, then rephrase their answer for a traveler who still needs a decision. Accept “I could not retrieve the board. I can still estimate your budget and look up weather if you give me an arrival time.”

**Voice rehearsal.** Use the same private HTTPS path as attendees. Listen to two consecutive spoken traveler turns. Start a separate Studio call, speak the brief and decline the confirmation aloud. During an approved live build, confirm once, review the artifact, then call the newly generated traveler agent and verify its second spoken turn. Record transcription, audible playback and tool evidence separately for each agent.

**Repeatable flight exercise.** Use the [two-date rehearsal](course/04-trip.md#run-the-two-date-case-on-your-own-agent) to test contradictory schedules with the same inputs on every run. `bash desk case status ZZ201` needs no credentials. Use the approval and Inspector steps to test the generated voice agent itself.
