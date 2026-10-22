# Run sheet: the three hours (software factories masterclass)

Thursday 22 October 2026, 14:30 to 17:30 London time (13:30 to 16:30 UTC), in person. You are the facilitator. This sheet runs the day. The slides are `slides/index.html` (30 slides, arrow keys), the book is `book/` and the factory is `factory/`.

Status: DRAFT. The times assume 180 minutes. If the event is set to 190, add the ten minutes to the work block. Lines marked (pending) wait for the factory console and its driver, and are filled in when they land.

## What the room leaves with
1. They saw the finished agent brief a traveler, with four cards, and every value on a card said where it came from.
2. They know the factory loop: a task, protected acceptance written first, a change made in a spare copy, an independent check and a recorded decision.
3. They watched the factory judge changes, and they saw a bad change stopped by a named check.
4. They have a book they can work through alone, from a clone, where each chapter shows a working part and then asks them to change it through the factory.

## The one lesson to say twice
The good change to the market card is one line, because the platform carries the work. The lesson is the gates.

## Three screens
| Screen | Address | Shows | Until |
| --- | --- | --- | --- |
| 1 | the factory console, port 8943 on the tailnet (pending) | the factory run, read-only | 17:30 London |
| 2 | the briefing agent, port 8942 on the tailnet | the Inspector and the four cards | 17:30 London |
| 3 | the deck, port 8944 on the tailnet | the slides, read-only | 17:30 London |

All three are readable by any device on the tailnet, and the Inspector on screen 2 is drivable from any tailnet device, which spends your OpenAI key and your Rasa license. Before the day, make sure only your own device can drive the Inspector (the setting for that is (pending: its name comes from the example's pull request)), or get the operator's explicit acceptance of the exposure. Keep the room's own devices off the tailnet. The console has no Run button: the builder starts from a terminal command (pending).

## Before the day
Do these on the facilitator machine, at least a day before and again an hour before.
- [ ] Clone with Git at the class commit named in the prework mail (`PREWORK.md` in this folder, with its addendum under `brief-me-before-i-fly/`). There is no zip.
- [ ] Your own license (`RASA_LICENSE`) and OpenAI key (`OPENAI_API_KEY`) are set in your shell. The doctor shows SET or MISSING and never a value. A Deepgram key is optional and only adds voice.
- [ ] The briefing agent starts from `examples/mantle-flight-briefing-openai-agents/` (`./demo setup`, then `./demo run`: the launcher is added by the class pull request for that example, PR 128, and is not in the repository until it merges) and the doctor is green.
- [ ] A real flight: ask the agent which flights are in the air headed to New York and pick one of the route-confirmed ones. If you use the fallback, a known callsign with a destination such as "callsign=DLH423 destination=EDDF", pick the airport from the table bundled with that example. The airport table for the fallback is (pending: the file is named when the example's pull request lands). Check an hour before, because flights land.
- [ ] The offline factory loop runs: copy `book/ready/ch06` to a new folder, set up Python as Chapter 6 says (`uv venv`, `uv pip install zeocore==0.35.4 httpx==0.28.1`), activate it, then `python run_a6.py tasks/a6-market-watchlist.json candidates/market-good` ends in ACCEPT and `candidates/market-shows-live` ends in REJECT. This needs macOS, because the check runs without network access inside `sandbox-exec`. Use the same folder for slide 28.
- [ ] The three screens load from a second device on the tailnet, and that second device can't type into the Inspector.
- [ ] The prework mail went out (`PREWORK.md` and its addendum). Its first step is the free Rasa Developer Edition license sign-up. Then Python 3.12 and uv, your own OpenAI key, and a clone with Git.
- [ ] Decide your fallbacks (see "If something fails") and say them aloud once.

## Run of show
Times are London, with UTC in brackets. "Show" is on screen and "Do" is what the room does. The slides carry the idea, so you can teach from them alone.

| Clock | Min | Block | Slides |
| --- | --- | --- | --- |
| 14:30 (13:30) | 15 | The problem and the finished agent | 1 to 7 |
| 14:45 (13:45) | 30 | The real question, the factory idea and the two tools | 8 to 26 |
| 15:15 (14:15) | 30 | We build the factory | 27 and 28 |
| 15:45 (14:45) | 95 | Your turn, with a break from 16:30 to 16:45 | 29 |
| 17:20 (16:20) | 10 | Close | 30 |

### 14:30 The problem and the finished agent (15 min)
Show: slides 1 to 4 (Sam, the agent and the plan), then slide 5 with screen 2, then slides 6 and 7. Do: watch.
Ask the agent which flights are in the air headed to New York, pick one of the route-confirmed flights it lists, then answer its meeting and transfer questions. Name each card as it appears and the label on it: source, computed, recording or failed. Say that a rate on the market card is a daily reference rate, not a live quote.
If voice isn't verified on the day, type the request and say so. Don't claim voice that you didn't see work.

### 14:45 The real question, the factory idea and the two tools (30 min)
Show: slides 8 to 26 in order. Do: listen. Questions wait for the work block. Each slide has one idea and one picture.
If you run short, skip in this order: slide 20 (the coin), slide 18 (two good changes clash), slide 19 (the dark factory), then slides 23 and 25. Slide 12 states the limit: a passing check proves only what it checks. Read it aloud.

### 15:15 We build the factory (30 min)
Show: slide 27, then slide 28 beside screen 1 (the console) and screen 2.
Say: "Nothing here is magic. We build it in the order of the book, and then we run it." Walk the five parts on slide 27 (the task, the tests, the builder, the gates, the integration), each with its book chapter. On slide 28, activate the environment and run the two commands in your chapter 6 folder: the good change ends in ACCEPT and the bad one in REJECT, naming the failed check.
The commands for the console and the live builder are (pending). The offline loop is the scripted builder from Chapter 6.
If the live builder stays in the run: there is no money cap per session, and the cap is the OpenAI project budget. Say the budget figure (pending: from the Architect), and the call limit and the time limit (pending: from the builder's documentation).
Say, at the end: "Nobody read the change. The gates decided. And the good change was one line, because the platform carries the work."

### 15:45 Your turn (95 min, with a break)
Show: slide 29 and leave it up. Do: everyone works through the book, alone or in groups of up to four, from Chapter 0. Each chapter has a ready folder, so anyone can start at any chapter.
Break: 16:30 to 16:45, with refreshments. Chat and networking are part of the plan.
Your job: walk the room. The three common stops are a missing license (point to the sign-up), a key that isn't set (the doctor shows SET or MISSING, never the value) and a clone made as a zip (clone with Git instead). Tell people that a live flight or a live builder run is an extra, and that every "done when" check works offline.
Say once at the start: "Keys and the license stay in your own shell or your own Git-ignored .env. Never put one in a tracked file, a tool result, a report or a chat."

### 17:20 Close (10 min)
Show: slide 30. Say what they built and where to go next: the book chapters, and the course "Towards Dark Software Factories" on profrod.ai. Ask what stopped them, and note it for the book.

## If something fails
| What fails | What you do |
| --- | --- |
| Voice | Type the request. Say voice wasn't shown today. |
| No flight is airborne, or the route is empty | Use the known callsign with a stated destination. If the source is down, the cards say unavailable with a reason. That is the honest state, so show it and say why. |
| A public source is slow | Wait once, then continue with the recorded four cards and say they're recorded. |
| The live builder fails | Run the scripted builder from Chapter 6 and the finished four-card version. Say clearly that these are a scripted builder and a finished version. |
| The console fails | Run the offline loop from a terminal with `run_a6.py` and show the decision lines. |
| The tailnet drops | Open the deck from the file in the repository. It needs no network. |

## What this day does not show
- It doesn't prove the factory is right. It shows a gate that catches the failures it checks for. An attempt that printed a hand-made valid card for every scenario would still pass.
- It doesn't show spoken input unless it worked in front of you, and it doesn't show a live flight unless one was airborne.
- The no-network check needs `sandbox-exec`, so it runs on a Mac.
- The class pages are readable by any device on the tailnet until they're stopped at 17:30 London time.
