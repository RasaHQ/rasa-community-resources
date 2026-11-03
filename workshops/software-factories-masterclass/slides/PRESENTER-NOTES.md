# Presenting the travel factory

## 1. Build a voice agent that builds travel agents · 00–01 MIN  /  WELCOME

Say: “You will make two different calls today. On the first, you want travel advice. On the second, you want new software.” Ask participants to open the workshop README in a second tab so they can launch their Codespace while you introduce the problem.

## 2. Which forecast belongs to my flight? · 01–02 MIN  /  THE TRAVELER

Ask: “If I tell you the temperature in Bergen right now, have I told you what to pack for landing?” Wait for “What time do I land?” Draw attention to the dependency: the flight lookup supplies the hour for the forecast. Then introduce the travel team that must maintain this behavior.

## 3. Tomorrow the travel team asks for a change · 02–04 MIN  /  THE ENGINEERING PROBLEM

Ask learners to name one observation that would convince them the change worked. Expected: a clarification on the ambiguous request, then a forecast for the selected record; the ordinary request still works. Say: “We have moved from answering a traveler to changing the software that answers them.”

## 4. How a request becomes a second agent · 04–06 MIN  /  THE FACTORY

Make the boundary concrete: the builder writes agent.json; the workshop compiler creates agent.yml, integrations.yml and the skill directory. Matching a hash identifies the reviewed bytes. Only testing the generated desk tells us how it handles the traveler. The factory itself is a Mantle agent when we operate it by voice.

## 5. What runs where? · 06–07 MIN  /  THE TOOLS

Point out that Codex and the hosted API are two build routes. The traveler’s weather question calls a provider; it does not start a build. No travel-data account is needed for the workshop route.

## 6. The route through the masterclass · 07–08 MIN  /  YOUR THREE HOURS

Show participants where they can pause: after the first voice call or after their first generated project. Transition: “Let’s get one real number into your hands before we open up the factory.”

## 7. Open the travel Codespace · 08–12 MIN  /  SET UP

Open the README launch link on the review branch for rehearsal. Do not project a secret. While dependencies install, learners can run the two Python data tools. Walk through profile picture → Settings → Codespaces → New secret. Show names only. The same Deepgram key powers both voices.

## 8. How much is $200 in pounds? · 12–17 MIN  /  FIRST LIVE RESULT

Let someone read their own number with its date. Use the deterministic test as a labeled example if the provider is unavailable. Ask learners to predict the result for $100 before rerunning the tool. Compare rate dates and rounding.

## 9. Ask for the right weather hour · 17–23 MIN  /  FIRST LIVE RESULT

Ask what extra information is required before making the second call. If the flight status has no arrival time, ask the traveler.

## 10. Call your first Mantle travel agent · 23–30 MIN  /  FIRST MANTLE AGENT

Wait for the server-ready message. Ask a learner which field supplied the exchange rate. If training is blocked, record the direct provider result and leave chat pending.

## 11. Where would you change this answer? · 30–40 MIN  /  READ THE PRODUCT

Have learners locate destination_weather and convert_currency. Ask why a two-tool starter cannot know whether a flight is delayed.

## 12. Write the brief for the full agent · 40–55 MIN  /  BUILD WITH CODEX

Use the exact commands in chapter 2. Ask learners to find the sentence that ties the arrival to the forecast. If access is delayed, use the labeled sample.

## 13. Turn the candidate into a Mantle project · 55–65 MIN  /  BUILD WITH CODEX

The displayed command wraps for projection; copy the single-line command in the workbook. The gate binds the bytes to the receipt. Review the authored behavior yourself. Once the full desk runs, use the chapter’s Codex editing exercise on a copy of the actual Mantle skill. Compare the two versions using an ambiguous destination.

## 14. What does “tonight” mean at Oslo? · 65–75 MIN  /  FLIGHT BOARD

Ask what happens at 23:30 UTC when Oslo is already on the next date. Keep unavailable, zero matches and sold out distinct.

## 15. Save your place · 75–85 MIN  /  BREAK

Give the full ten minutes. Someone running at home can stop the same Codespace here.

## 16. Two Mantle agents have different customers · 85–98 MIN  /  FACTORY ARCHITECTURE

Ask which agent needs the aviation provider and which starts a hosted session. Make participants identify the two different Inspector conversations.

## 17. How do the bytes leave the hosted workspace? · 98–110 MIN  /  HOSTED AGENTS API

Ask if a “done” message with only notes.txt is enough. It is not. The workshop uses the hosted Agents API; a local Runner is not involved.

## 18. Commission a Bergen-to-Oslo desk · 110–125 MIN  /  OPERATE THE FACTORY

If the result is uncertain, keep the run and inspect it before any retry. Use the sample route if the class is working without hosted access.

## 19. Run the agent Studio commissioned · 125–135 MIN  /  RUN THE PRODUCT

Ask a traveler question, not a build request. Require the product tool event; successful generation alone cannot establish that the agent answers the trip. End the Studio call and start a new voice call to the generated product. Require two spoken turns, audible replies and tool events.

## 20. Produce a briefing someone can act on · 135–150 MIN  /  TRIP CHALLENGE

Open one tool event with the room. If there are several matches ask for clarification. If Avinor is unavailable, continue with FX and an explicitly timed weather request.

## 21. One flight number. Two possible forecasts. · 150–157 MIN  /  PREDICT

Give the room 30 seconds to choose the first response. Run bash desk case status ZZ201. Ask for the weather hour on each date. Never use this invented flight as live travel data.

## 22. Call the generated desk with the same two records · 157–165 MIN  /  REHEARSE

Start a fresh call for November fourth; expect the scheduled hour and 7 °C. Ask learners to show the order of status, clarification and weather. Restore live providers with bash desk inspect builds/studio-desk.

## 23. What will you ask the factory to build next? · 165–180 MIN  /  TAKE IT HOME

Have one learner explain how Codex authors the spec and where the hosted service returns its artifact. Save notes, stop the Codespace and show chapter 4 for resuming.
