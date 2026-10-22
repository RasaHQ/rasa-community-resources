# Run sheet: the three hours (software factories masterclass)

Thursday 22 October 2026, 14:30 to 17:30 London time (13:30 to 16:30 UTC), in person. You are the facilitator. This sheet runs the day. The slides are `slides/index.html` (30 slides, arrow keys), the book is `book/` and the factory is `factory/`.

Status: DRAFT. The times assume 180 minutes. If the event is set to 190, add the ten minutes to the work block. The console and driver commands below require the factory changes in PR 133. Remaining `(pending)` items need an explicit decision before use.

## What the room leaves with
1. They saw the finished agent brief a traveler, with four cards, and every value on a card said where it came from.
2. They know the factory loop: a task, protected acceptance written first, a change made in a spare copy, an independent check and a recorded decision.
3. They watched the factory judge changes, and they saw a bad change stopped by a named check.
4. They have a book they can work through alone from a clone, with supplied checkpoints and factory exercises.

## The one lesson to say twice
The good change to the market card is one line, because the platform carries the work. The lesson is the gates.

## Three screens
| Screen | Address | Shows | Until |
| --- | --- | --- | --- |
| 1 | the factory console, port 8943 on the tailnet (PR 133) | the factory run, read-only | 17:30 London |
| 2 | the briefing agent, port 8942 on the tailnet | the Inspector and the four cards | 17:30 London |
| 3 | the deck, port 8944 on the tailnet | the slides, read-only | 17:30 London |

All three are readable by any device on the tailnet, and the Inspector on screen 2 is drivable from any tailnet device, which spends your OpenAI key and your Rasa license. Before the day, declare who may drive the Inspector with the setting `BRIEFING_VIEWER_ACCESS` (in the class example's pull request, PR 128). Its value is `operator-device-acl` after an access list limits the ports to your device, or `operator-accepted` with the operator's explicit acceptance. The setting declares the choice and does not set up the access list for you, and a tailnet launch is refused without one of the two values. Recheck its name and values if that pull request changes before the class. Keep the room's own devices off the tailnet. The console has no Run button: the builder starts from a terminal command (see Run of show).

## Before the day
Do these on the facilitator machine, at least a day before and again an hour before.
- [ ] Clone with Git at the class commit named in the prework mail (`PREWORK.md` in this folder, with its addendum under `brief-me-before-i-fly/`). There is no zip.
- [ ] Your own license (`RASA_LICENSE`) and OpenAI key (`OPENAI_API_KEY`) are set in your shell. The doctor shows SET or MISSING and never a value. A Deepgram key is optional and only adds voice.
- [ ] The briefing agent starts from `examples/mantle-flight-briefing-openai-agents/` (`./demo setup`, then `./demo run`: the launcher is added by the class pull request for that example, PR 128, and is not in the repository until it merges) and the doctor is green.
- [ ] The opening runs the labeled SCRIPTED selector over the real public sources. The data is real and teaching code makes the tool choices, so say so plainly: slide 5 says it too. Ask "Which flights are in the air heading to New York?", answer "that one" for the flight it picks, then say your meeting time at the destination in local time. The agent assumes a typical transfer time and labels it as an assumption: say "make the transfer an hour" to revise it. This must be frozen and rehearsed by 08:30 UTC. If it isn't, the fallback is the recorded opening, a recorded flight with its REPLAY label said aloud. The OpenAI Agents API appears later, in the recording of the funded builder run in the factory part. Check an hour before, because flights land. The airport table for a stated destination is (pending: the file is named when the example's pull request lands).
- [ ] The offline factory loop runs: copy `book/ready/ch06` to a new folder, set up Python as Chapter 6 says (`uv venv`, `uv pip install zeocore==0.35.6 httpx==0.28.1`), activate it, then `python run_a6.py tasks/a6-market-watchlist.json candidates/market-good` ends in ACCEPT and `candidates/market-shows-live` ends in REJECT. This needs macOS, because the check runs without network access inside `sandbox-exec`. Use the same folder for slide 26.
- [ ] The three screens load from a second device on the tailnet, and that second device can't type into the Inspector.
- [ ] The prework mail went out (`PREWORK.md` and its addendum). Its first step is the free Rasa Developer Edition license sign-up. Then Python 3.12 and uv, your own OpenAI key, and a clone with Git.
- [ ] Decide your fallbacks (see "If something fails") and say them aloud once.

## Rehearsal and freeze
Before the event the team runs this sheet in order against versions that are then frozen, with no one testing it for the first time on the day. Rehearsal is 07:30 to 08:30 UTC: the opening demo, the deck read aloud and timed, the live factory build and run, and every book chapter from a clean clone by someone other than its author. The opening must run on Core 0.36.0 or later. Earlier releases read only the first 100 aircraft in the find-flights step, so near New York they can answer "no flights found" while flights exist, which would trigger the scripted fallback falsely. Note the Core version the opening ran on in the rehearsal result. The book chapters use their own environments, so Chapters 6 and 7 install zeocore 0.35.6 in their own folders while the opening runs in the class example's environment on 0.36.0 or later. Keep the two apart. Each failure is fixed or cut with a plain note. The freeze is at 08:30 UTC, after which only rehearsal fixes go in. At about 09:10 UTC the facilitator receives the links, the rehearsal result and what needs a decision.

## Run of show
Times are London, with UTC in brackets. "Show" is on screen and "Do" is what the room does. The slides carry the idea, so you can teach from them alone.

| Clock | Min | Block | Slides |
| --- | --- | --- | --- |
| 14:30 (13:30) | 15 | The problem and the finished agent | 1 to 7 |
| 14:45 (13:45) | 30 | The real question, the factory idea and the two tools | 8 to 24 |
| 15:15 (14:15) | 30 | We build the factory | 25 to 27 |
| 15:45 (14:45) | 95 | Your turn, with a break from 16:30 to 16:45 | 28 and 29 |
| 17:20 (16:20) | 10 | Close | 30 |

### 14:30 The problem and the finished agent (15 min)
Show: slides 1 to 4 (the plan, Sam and the agent), then slide 5 with screen 2, then slides 6 and 7. Do: watch.
Slide 5 reads "A script picks the tools" (deck head 9c866309). The example is the approved PR 128 head c6596de1 on Core 0.36.3. Its rehearsal ran the greeting, three source-backed choices, the first pick, the 6 pm meeting tomorrow and four available cards in 2.4 seconds from the pick. The sources are real and are not a recording. Voice was tested and did not complete a four-card spoken journey. The synthesized speech reached the agent and the first question returned four choices, but the second spoken reply produced no answer. The microphone and browser path is untested. Type the request, and don't claim voice. Say: "The data is real. The choice of tools is scripted. Later you'll see a recording of the model building." Ask "Which flights are in the air heading to New York?", answer "that one" for the flight it picks, then say your meeting time at the destination in local time. Point out that the transfer time is a labeled assumption, then change it by saying so. If the scripted opening wasn't frozen and rehearsed, run the recorded opening and say it is a recording.
If voice isn't verified on the day, type the request and say so. Don't claim voice that you didn't see work.

### 14:45 The real question, the factory idea and the two tools (30 min)
Show: slides 8 to 24 in order. Each part opens with what the room will understand and closes with an in-short line and what comes next. Do: listen. Questions wait for the work block. Each slide has one idea and one picture.
If you run short, skip in this order: slide 19 (the coin), slide 17 (two good changes clash), slide 18 (the dark factory), then slide 23. If you skip slide 23, say its two points aloud: a run has limits (time and tool calls), and a key stays in your shell or a Git-ignored `.env` file. The book's setup step says it too. Slide 11 states the limit: a passing check proves only what it checks. Read it aloud.

### 15:15 We build the factory (30 min)
Show: slide 25, then slide 26 beside screen 1 (the console) and screen 2, then slide 27.
Say: "Nothing here is magic. We build it in the order of the book, and then we run it." Walk the five parts on slide 25 (the task, the tests, the builder, the gates, the integration), each with its book chapter. On slide 26, activate the environment and run the two commands in your chapter 6 folder: the good change ends in ACCEPT and the bad one in REJECT, naming the failed check.
The console and the builder driver come with the factory console pull request (PR 133). Their shapes, to recheck against that pull request before class, run from `factory/`: the offline scripted builder, `python agent-runs/drivers/qualify_scripted_builder.py <pack folder> <work folder>`, with a new work folder each run; the console, `python factory_console.py <work folder>/run --port 8943`, started before the driver, which serves on 127.0.0.1 only (for the tailnet screen add `--host <tailnet address>` and `--expires-at <the end of the class as an ISO time with its zone>`, plus the required `--viewer-access` declaration described below, or show the console from your own screen); and the live builder only after you have stated its expected cost, with `python agent-runs/drivers/openai_factory_driver.py <task> <prepared scratch folder> <new run folder> --model <model> --pack-root <A6 pack folder> --environment environment-a6.json --no-session-cap --expected-cost-cents-min <min> --expected-cost-cents-max <max>`. The expected cost is a range you state and not a cap. Prepare the scratch folder first with `scratch.py`, which never copies the protected tests. Keys are never put on a command line.
For a tailnet console, `--viewer-access operator-device-acl` declares that an actual access list already limits the audience. Alternatively, `--viewer-access operator-accepted` requires the operator's explicit acceptance of the wider audience. Neither flag creates an access list. A tailnet launch without the declaration is refused. For this event the expiry is `2026-10-22T16:30:00Z`. Keep the existing preview running; do not start another process on its occupied port.

Say these two limits in plain words before the build:
- "The factory builds and tests the market card. You see the recording of a funded model build, which used 8 tool calls, took about 37 seconds and passed all 14 checks. Then you see a live run of the scripted builder, with no model calls. Today it doesn't install the new card into the running demo."
- "Chapters 1 and 2 are short concept chapters. They have no change exercise today."

### Qualification already completed, and what it does not establish

- The factory's funded qualification completed once with Standard `gpt-6-astra` and Core 0.35.6: eight file-tool calls, about 37 seconds, and all 14 protected market-card checks passed. This was a real builder session. Its expected cost range was 15 to 150 US cents; the provider returned no usage record, so billed cost remains **unmeasured**. Do not present the range as actual cost or a per-session cap.
- Independently tested book Chapters 3, 4, 6 and 7 at PR130 `b985f833`: both reader choices, one and three currencies, passed in clean copies with no keys. Each documented completion check failed before the exercise and passed afterward. Chapter 7's sample HTML was rendered and explicitly says its numbers are samples.
- Applying the funded proposal to the running Mantle agent, restarting it and seeing its market card is a separate acceptance step. It is **not recorded** by the factory's ACCEPT. Until that receiving check passes, use the scripted builder and finished agent as the stated fallback; do not describe them as a demonstrated funded end-to-end build.

No funded builder run happens live today. The room sees the recording of one. If a live funded run is ever added, it is bounded locally (steps, a time limit and one model), and the hard cap is the project budget in the OpenAI account. Before the class, check in the account that the project budget enforces a hard limit and doesn't only send alerts (https://developers.openai.com/api/docs/guides/spend-limits). A hard limit can overshoot slightly. State the expected cost and say the budget figure (pending: from the Architect). Each run is limited to 16 tool calls, a 60 second deadline and 20 second timeouts in the class example, and 30 tool calls and a 120 second deadline in the factory builder. Recheck the limits if either pull request changes before the class.
Say, at the end: "Nobody read the change. The gates decided. And the good change was one line, because the platform carries the work."

### 15:45 Your turn (95 min, with a break)
Show: slide 28 and leave it up. At 16:30 show slide 29 (the break). At 16:45 go back to slide 28. Do: everyone works through the book, alone or in groups of up to four, from Chapter 0, then the short Chapters 1 and 2 (reading only, their change steps follow after the class), then Chapter 3. Each chapter has a ready folder, so anyone can start at any chapter.
Break: 16:30 to 16:45, with refreshments. Chat and networking are part of the plan.
Your job: walk the room. The three common stops are a missing license (point to the sign-up), a key that isn't set (the doctor shows SET or MISSING, never the value) and a clone made as a zip (clone with Git instead). Tell people that a live flight or a live builder run is an extra, and that the "done when" checks in Chapters 1 to 8 work offline after the one-time install. Chapter 0 needs the license and an internet connection for the install, then runs on recorded data. Only its optional live-source extra needs the internet while it runs.
Say once at the start: "Keys and the license stay in your own shell or your own Git-ignored .env. Never put one in a tracked file, a tool result, a report or a chat."

### 17:20 Close (10 min)
Show: slide 30. Say what they built and where to go next: the book chapters, and the course "Towards Dark Software Factories" on profrod.ai. Ask what stopped them, and note it for the book.

## If something fails
| What fails | What you do |
| --- | --- |
| Voice | Type the request. Say voice wasn't shown today. |
| No flight is airborne, or the route is empty | Run the recorded opening and say it is a recording. If a source is down, the cards say unavailable with a reason. That is the honest state, so show it and say why. |
| A public source is slow | Wait once, then continue with the recorded four cards and say they're recorded. |
| The recording of the funded build won't play | Run the scripted builder from Chapter 6 and the finished four-card version. Say clearly that these are a scripted builder and a finished version. |
| The console fails | Run the offline loop from a terminal with `run_a6.py` and show the decision lines. |
| The tailnet drops | Open the deck from the file in the repository. It needs no network. |

## What this day does not show
- The model choosing the tools live in the opening is not shown today. In the factory part you see the recording of the model building, and a live run of the scripted builder. The model is not live.
- It doesn't install the factory's new market card into the running demo. The factory builds and tests the card, and the room sees the recorded build and a live safe run.
- Chapters 1 and 2 have no change exercise today. They show the parts and where card data comes from.
- It doesn't prove the factory is right. It shows a gate that catches the failures it checks for. An attempt that printed a hand-made valid card for every scenario would still pass.
- It doesn't show spoken input unless it worked in front of you, and it doesn't show a live flight unless one was airborne.
- The no-network check needs `sandbox-exec`, so it runs on a Mac.
- The class pages are readable by any device on the tailnet until they're stopped at 17:30 London time.
