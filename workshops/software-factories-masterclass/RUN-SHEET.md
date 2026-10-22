# Three hours: demo, explanation, group work

Use elapsed time. If the booked start is 14:30 London, the finish is 17:30. This replaces all earlier competing schedules in the archive.

| Elapsed | Example clock | Activity | Evidence / output |
|---|---|---|---|
| 00–10 | 14:30–14:40 | Teaser: the finished travel experience, then the build loop | Typed question (voice failed on the second turn in today's audio-file test), visual cards, one rejected change. Identify live, replay and scripted parts before showing them. |
| 10–30 | 14:40–15:00 | Concepts, slides 4–16 | Participants can explain the two agents, independent verification and release boundary. Spend about 1 minute on each of slides 4 to 8 and about 1.5 minutes on each of slides 9 to 16, which is 17 minutes with a few spare. |
| 30–40 | 15:00–15:10 | Form groups of 3–4; open the guide; choose track | One driver, one requirements owner, one evaluator, optional observer. |
| 40–95 | 15:10–16:05 | Lab A at each group's pace | Brief, acceptance examples, first attempt and recorded verdict. |
| 95–110 | 16:05–16:20 | Break and meet another group | Each group exchanges one failure case. |
| 110–165 | 16:20–17:15 | Lab B at each group's pace | A rejection, revised attempt, integration evidence and a handoff. |
| 165–180 | 17:15–17:30 | Three short group demos and closing discussion | Show the requirement, failed case, result and remaining limitation. |

110 minutes of lab plus 15 minutes of networking = 125 minutes, 69% of the session. Do not add a second lecture during the labs. Optional appendix slides answer questions at tables.

## Teaser script (10 minutes)

1. Show the travel assistant immediately. State: “Tool selection is scripted. Voice failed on the second turn in today's audio-file test. I will type.” Use the chapter 0 recorded prompts for a dependable teaser, or a separately rehearsed current-source run. For the recorded route, type “United 1162 to EWR”, then “The 6 pm meeting tomorrow.” For a rehearsed current-source route, ask for New York flights and choose a returned option. Show the four cards, then type “Allow 120 minutes to get into town.” The timeline must update without changing the flight. Ask “What if the weather source is down?” Show the failure state from a labeled fixture if necessary.
2. Show the factory's task and accepted artifact, then one rejected attempt. Point to the actual check that rejected it.
3. Explain the destination: “We want to describe this assistant by voice, have a builder make it, and release only the version that passes our checks.” If the full bridge has not passed rehearsal, say “Today these are two connected ideas demonstrated in separate components. Wiring the complete path is our extension.”

The live builder defaults to the model gpt-6-astra. The scripted path never calls it. If a live run happens, state its expected cost range first: 15 to 150 US cents is an estimate, not a cap, and the billed cost was not measured.

Never narrate a prerecorded or scripted build as a live model run. Never describe the supplied currency-card extension as generating an entire application from nothing.

## Before opening the room

The opening runs on the class preview at port 8942: PR 140 head 8427cf8f, Core 0.36.3, Rasa Pro 3.21.0.dev5 (the standalone example), typed and labeled SCRIPTED over real public sources. In one measured run at 11:58 UTC the agent suggested a named flight (Delta Air Lines 2524 to LGA), and 2.5 seconds after "that one" four available cards showed, including the meeting reply. That is one run, not a promise of speed. Voice was tested with Deepgram audio files today and failed on the second turn, so type your requests. The microphone path is untested. The Deepgram file test ran at 12:05 UTC.

Read `TECHNICAL-AUDIT.md` and perform the rehearsal in `FACILITATOR.md`. Give participants this exact revised package rather than an unspecified GitHub main branch. Have two independently set-up laptops for the main route. Test microphone permissions and audio output in the actual room. Record the runtime versions and the mode of each demo. Credentials remain on each group's machine.

At minute 50, any group still installing moves to the data-only track. At minute 145, freeze new features and prepare the evidence. At minute 165, stop lab work. A working, explained rejection is a valid result.
