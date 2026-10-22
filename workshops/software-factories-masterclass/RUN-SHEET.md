# Run sheet: the three hours (software factories masterclass)

Thursday 22 October 2026, 13:30 to 16:30 UTC (14:30 to 17:30 London time), in person. You are the facilitator. This sheet runs the day. The slides are `slides/index.html`, the book is `book/`, and the factory is `factory/`.

Status: DRAFT. The times assume 180 minutes. If the event is set to 190, add the ten minutes to Block 5. Lines marked (pending) wait for the factory console and its driver, and are filled in when they land.

## What the room leaves with
1. They saw the finished agent brief a traveler by voice, with four cards, and every value on a card said where it came from.
2. They know the dark software factory loop: a task, a protected acceptance written first, an isolated change, an independent check and a recorded decision.
3. They watched a factory get built in front of them, and they saw the market card appear in the agent without anyone reading the builder's code.
4. They have a book they can work through alone, from a clone, that builds the same factory step by step.

## The one lesson to say twice
The good change to the market card is one line, because the platform carries the work. The lesson is the gates, not the code.

## Three screens
| Screen | Address | Shows | Until |
| --- | --- | --- | --- |
| 1 | the factory console, port 8943 on the tailnet (pending) | the factory being built and run | 16:30 UTC |
| 2 | the briefing agent, port 8942 on the tailnet | the Inspector and the four cards | 16:30 UTC |
| 3 | the deck, port 8944 on the tailnet | the slides, read-only | 16:30 UTC |

All three are readable by any device on the tailnet. Say so to the room and keep the room's own devices off the tailnet if that matters to you.

## Before the day
Do these on the facilitator machine, at least a day before and again an hour before.
- [ ] Clone with Git at the class commit named in the participant mail. There is no zip.
- [ ] Your own license (`RASA_LICENSE`) and OpenAI key (`OPENAI_API_KEY`) are set in your shell. The doctor shows SET or MISSING and never a value. A Deepgram key is optional and only adds voice.
- [ ] The briefing agent starts from the example (`./demo setup`, then `./demo run`) and the doctor is green.
- [ ] A real flight: pick a callsign that is airborne now from the public source, and a destination airport from the class table. Rehearse the sentence you will say or type, for example "callsign=DLH423 destination=EDDF". Re-check an hour before, because flights land.
- [ ] The factory loop runs offline: from `factory/a6-market-watchlist/`, `python run_a6.py tasks/a6-market-watchlist.json candidates/market-good` ends in ACCEPT, and each of the three bad candidates ends in REJECT. This needs macOS, because the check runs without network access inside `sandbox-exec`.
- [ ] The three screens load from a second device on the tailnet.
- [ ] The prework mail went out. Its first step is the free Rasa Developer Edition license sign-up. Then Python 3.12 and uv, your own OpenAI key, and a clone with Git.
- [ ] Decide your fallbacks (see "If something fails") and say them aloud once.

## Run of show
All times UTC. "Say" is yours in your own words, "Show" is on screen, "Do" is what the room does.

| Clock | Min | Block |
| --- | --- | --- |
| 13:30 | 15 | 1. The end result |
| 13:45 | 30 | 2 and 3. The ideas and the two tools |
| 14:15 | 30 | 4. We build the factory |
| 14:45 | 95 | 5. On your own, with a break |
| 16:20 | 10 | 6. Close |

### 13:30 The end result (15 min)
Show: slides 1 to 4, then screen 2. Do: nothing yet, just watch.
Say: "Here's what you'll be able to build by the end of today. I'll talk to the agent." Speak or type a real flight, for example "callsign=DLH423 destination=EDDF". Name each card as it appears and the label on it: PROVIDER DATA, COMPUTED, REPLAY or unavailable.
Watch for: the flight card, the weather at the destination, the arrival timeline and the market watchlist. Say aloud that a rate on the market card is a daily reference rate, not a live quote.
If voice isn't verified on the day, type the request and say so. Don't claim voice that you didn't see work.

### 13:45 The ideas and the two tools (30 min)
Show: the deck, parts A, B and C (slides 5 to 47). Do: listen. Questions wait for Block 5. Every part opens with what the room will understand and ends with a recap, and each new term is defined with a small example before it is used.
Part A is slides 5 to 25. If you run short, cut in this order: the integration slide (17), then the escalation slide (22), then the supervision-policy slide (21), and keep the bridge slide (24) last. Part B is slides 26 to 33 and part C is slides 34 to 47. The deck is built to teach from zero, so it holds more slides than 30 minutes allows at a steady pace. Skip the definition slides for words the room already knows, and say so. The timing is open with the Architect.
Say the limit aloud on the slide that states it: a gate proves only what it checks.

### 14:15 We build the factory (30 min)
Show: slides 48 to 53 on screen 3, screen 1 (the console) and screen 2 side by side. Say: "Nothing here is magic. I'll build it in the order of the book, and then we run it."
| Min | Part | What you do and say |
| --- | --- | --- |
| 4 | The task | The prompt, the two allowed paths and the pins. Book chapter 3. |
| 6 | The acceptance | The protected suite, written before any code, and the baseline failing it for the right reasons. Chapter 4. |
| 6 | The builder | An OpenAI Agents API session whose file tools reach only a scratch copy. Chapter 5. |
| 7 | The gates and the decision | The good candidate is ACCEPTed. The three bad ones are stopped: a rate shown as live, an invented rate when the source fails, an edited protected suite. Chapter 6. |
| 7 | Integration, then run | ACCEPT integrates the change, the agent restarts and the fourth card appears on screen 2. Chapter 7. |
The commands for the console and the live builder are (pending). The offline loop is `python run_a6.py` as in "Before the day".
Say, once the card appears: "Nobody read the builder's code. The gates decided. And the change was one line, because the platform carries the work."

### 14:45 On your own (95 min, with a break)
Show: slide 54 (the hand-off to the book). Do: everyone works through the book, alone or in groups of up to four, from chapter 0. Anyone can start at any chapter from its checkpoint.
Break: 15:30 to 15:45, with refreshments. Chat and networking are part of the plan.
Your job: walk the room. The three common stops are a missing license (point to the sign-up), a key that isn't set (the doctor shows SET or MISSING, never the value) and a clone made as a zip (clone with Git instead). Tell people that a live flight or a live builder run is an extra, and that every "done when" check works offline.
Say once at the start: "Keys and the license stay in your own shell or your own Git-ignored .env. Never paste one into a file in the repository or into a chat."

### 16:20 Close (10 min)
Show: slides 55 to 57 (part D). Leave the three glossary slides (58 to 60) up during the break. Say what they built and where to go next: the book chapters, and the course "Towards Dark Software Factories" on profrod.ai. Ask what stopped them, and note it for the book.

## If something fails
| What fails | What you do |
| --- | --- |
| Voice | Type the request. Say voice wasn't shown today. |
| No flight is airborne, or the route is empty | Use the callsign with a stated destination. If the source is down, the cards say unavailable with a reason. That is the honest state, so show it and say why. |
| A public source is slow | Wait once, then continue with the recorded four cards and say they're recorded. |
| The live builder fails | Run the recorded builder runs and the finished four-card version. Say clearly that they're recorded and finished, not live. |
| The console fails | Run the offline loop from a terminal with `run_a6.py` and show the decision lines. |
| The tailnet drops | Open the deck from the file in the repository. It needs no network. |

## What this day does not show
- It doesn't prove the factory is right. It shows a gate that catches the failures it checks for. A candidate that printed a hand-made valid card for every scenario would still pass.
- It doesn't show spoken input unless it worked in front of you, and it doesn't show a live flight unless one was airborne.
- The no-network check needs `sandbox-exec`, so it runs on a Mac.
- The class pages are readable by any device on the tailnet until they're stopped at 16:30 UTC.
