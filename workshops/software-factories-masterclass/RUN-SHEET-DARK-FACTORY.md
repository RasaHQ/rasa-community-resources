# Run sheet: build a dark software factory with Rasa Mantle and the OpenAI Agents API

sow: public

Three hours. Minutes count from the start. This sheet is for the session that uses GitHub Codespaces. It says what each person builds and sees, minute by minute. All times below are planned targets. Nobody has yet confirmed that a first-time attendee can reach them. The evidence table near the end says what was observed, by whom, and what is still open.

## The one small agent: the router restart helper

Everyone builds the same small agent, and later an agent that uses the OpenAI Agents API (application programming interface, or API). A customer says "restart my router". The helper asks them to confirm, then records a restart command and nothing else. It never records a factory reset, which would erase the customer's Wi-Fi name and password. The workshop simulates the command. It does not contact a router or change anyone's internet connection.

Why this agent:

- It is small enough to build in a short time.
- It has one real risk: a restart and a factory reset sound alike and do very different things. That makes the value easy to see (a confirmation, then the right command) and gives the later blocks something to check.
- A public exercise and a Mantle example already exist for the same situation (the router-support example in this repository).

You can tell it works when:

1. "Restart my router" makes the helper ask you to confirm.
2. "Yes" makes it record one command, `REBOOT`.
3. "Reset it" makes it ask which one you mean, and it sends nothing until you answer.
4. A request for a factory reset makes it say it cannot do that here and offer help from a person. It records no factory-reset command.

## One path: Rasa Mantle

Everyone builds on Rasa Mantle: the Mantle Inspector, a skill file, a tool, and an installer script that makes a fresh Mantle agent into the helper. Then the rest of the session grows the helper into a station on a dark software factory.

**Studio 2 preview (presenter only).** At a point the presenter chooses, the presenter shows a Studio 2 preview from their own machine. It is an early preview that attendees cannot try yet. The presenter ends it with a call to action: join the Rasa Community at https://info.rasa.com/community/ to hear when Studio is released. Nothing in this workshop needs it, and attendees do nothing for it.

## At a glance (planned targets)

| Minutes | Block | You build | You see | Target result |
|---|---|---|---|---|
| 0 to 10 | The result | Nothing yet. Everyone opens a codespace | The finished helper handling the four checks above | You know what "working" means |
| 10 to 30 | Your router helper | Install, train, inspect | Your helper asking to confirm and recording `REBOOT` | All four checks |
| 30 to 50 | Reset handling and your own change | Your own wording and requests against the helper | How it handles a changed mind and a reset request | The helper never records anything you did not ask for |
| 50 to 70 | Source-file check | A check that reads the configured restart command | The check passing, then failing when the file says `FACTORY_RESET` | A check the helper's replies cannot satisfy |
| 70 to 75 | Break | | | |
| 75 to 90 | The factory begins: your builder | An OpenAI Agents API agent that you create, with your own key | Its session events and the file it saves | Your builder agent has proposed a change |
| 90 to 115 | The builder behind the helper | A small tool server that hands a request to your builder | The helper calling your builder | A request goes in and a proposed change comes out |
| 115 to 140 | The gate | A deliberately bad change, and the gate run on both | One change accepted, one rejected, and the name of the failing test | A line that can say no |
| 140 to 160 | Release | The final human gate and a decision record | You approving or refusing one change | The line run once, end to end |
| 160 to 175 | Voice (drop first if time is short) | Speech switched on for the Mantle helper | The same helper answering by voice | Voice on the same helper |
| 175 to 180 | Close | Nothing | The line with your pieces on it | A take-home recap |

If time is short, drop voice first. Then shorten the release block. Never shorten the first 30 minutes.

## Minutes 0 to 10: the result

Say: "Our target for the first 30 minutes is a small restart helper that asks for confirmation. We will test it together. After that we turn it into a station on a dark software factory. That is a production line where nobody reads each change as it passes. Agents do the work. Checks that the agents cannot edit decide what moves on. A person stands at a few defined gates."

Show: the finished helper, once, handling the four checks above. No other demo. Say that the command is simulated.

**Everyone opens their codespace now, at minute 0, while the result is on the screen.** The setup includes an install that can run for several minutes after the codespace shows as available. Wait for the setup to print its finished line before you start building at minute 10 to 15. The presenter tracks setup time and helps anyone who is stuck.

## Minutes 10 to 30: your router helper

In a new folder, run `rasa init --engine mantle --no-prompt`, then the installer `router-helper/mantle/install_helper.py` on that folder, then `rasa train`, then `rasa inspect --port 5010`, and open the Inspector address. The installer moves the starter banking skills out of the active skills and sets a router-only persona and rules. Then run the four checks.

You build: the helper.
You see: the confirmation, then `REBOOT` recorded.
Target at minute 30: all four checks.

The exact steps are in the attendee pack. The files are in `router-helper/`.

## Minutes 30 to 50: reset handling and your own change

Everyone works the four checks again in a different order and in their own words: a changed mind, a reset asked for in different words, a factory reset asked for outright. Put these questions to the room:

- Who wrote the confirmation, you or the engine?
- Where is the command `REBOOT` stored?
- What does the helper keep as files?

Target at minute 50: a helper that never records anything the customer did not ask for.

## Minutes 50 to 70: the source-file check

The helper must never record `FACTORY_RESET` when asked to restart. A check can look at the configured restart command in a file instead of at what the helper said.

Run `router-helper/check_helper.py` on the Mantle tool file. It reads the configured command and fails if it is not `REBOOT`. Then change the file to `FACTORY_RESET` and run the check again. It fails, and names why.

You build: a source-file check.
You see: the check pass, then fail on the wrong command, even though the helper's reply could still sound right.
Target at minute 70: a check that reads the configured command, not the reply.

This is a source-file check of the configured restart command. It does not watch a live conversation, so a pass does not prove the helper ran that command at run time. It exits 2 when it cannot find a command, so a missing command is never a pass. If every check passes by minute 70, people who leave then have a working helper and a check for it.

## Minutes 75 to 115: the factory begins, with the OpenAI Agents API

Now the helper becomes the front desk of a factory. The factory's builder is an agent you create with the OpenAI Agents API, using your own key.

**Minutes 75 to 90: create your builder.** You choose the model and write its instructions, run a session, and watch the stream of events. The task is a small change to the helper: add one read-only operation, "check line status". The agent works in OpenAI's hosted sandbox and reports what it wrote.

Facts from OpenAI's Agents API quickstart (read Nov 2): your key needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write`. A session starts with `client.beta.agents.sessions.create(...)`. An agent is a model, instructions, tools, and optional MCP servers. Model use is billed at the model's API rates.

**Minutes 90 to 115: put the builder behind the helper.** A small tool server wraps your builder. On the Mantle path, run the `change_builder` installer, then train and open the Inspector again, as the attendee pack shows. The installer copies the skill into the agent's `skills/` folder and raises Mantle's tool wait from 10 seconds to at least 450, because a build takes minutes. The skill's tool calls the server and shows the customer the build id, saved flag, file path, and sha256.

You build: your builder agent, and the connection to it.
You see: the session's events, then the helper calling your builder and showing the proposed change.
Target at minute 115: a request goes in and a proposed change comes out.

The code is in `router-helper/builder/`: `builder.py` (your agent, with the instructions you edit) and `builder_server.py` (the tool server), with a README for the Mantle wiring.

## Minutes 115 to 140: the gate

Run the gate on your builder's change. Then run it on a deliberately bad change that records `FACTORY_RESET`. The gate names the test that rejected it, and neither the builder nor the helper can edit it.

You see: one ACCEPT, one REJECT, and the name of the failing test.
Target at minute 140: a line that can say no.

The gate is `router-helper/gate/gate.py`, with a good change and three bad ones in `router-helper/gate/candidates/`. It accepts only a file that holds one function, `check_line_status()`, with no arguments and one statement: a return of a dictionary written out as plain values. It reads the file once and judges those bytes. It never runs the change, so a change cannot write a file or open the network while it is judged. This fits one small read-only operation and is not a general sandbox.

## Minutes 140 to 160: release

Run the whole line once: ask the helper for the change, let the builder propose it, let the gate judge it, then approve or refuse as the person at the last gate. Record your decision.

Target at minute 160: one change built, checked, and released or refused by you.

## Minutes 160 to 175: voice (drop first)

Switch speech on for the helper. Mantle's docs list the speech providers and their keys, which attendees may not have. Drop this block if time is short.

## Minutes 175 to 180: close

Show the line again with the pieces each person built. Name the one check each person could not edit. Hand out the recap.

## If a station fails: the fallback at each stage

| Stage | If this breaks | Fall back to |
|---|---|---|
| Minutes 0 to 30 | A codespace will not open or the setup stalls | Pair with a neighbor who has one. The presenter keeps one working codespace for the room. |
| Minutes 0 to 30 | Your key or license is rejected | Say so at once. Watch your neighbor's path until a key is fixed. Never retry a key that was rejected. |
| Minutes 10 to 50 | The helper will not work | Pair with a neighbor whose helper works. If it still fails, follow the presenter's demonstrated or recorded example, and note which parts you could not complete. |
| Minutes 50 to 70 | The check cannot find a command | Read the exit code. 2 means it found nothing, and the file layout is the first thing to look at. |
| Minutes 75 to 115 | Your Agents API session fails (permissions, quota, model) | The presenter runs one builder on the screen. You watch its events and take the saved change in `router-helper/gate/candidates/good.py` to the next block. |
| Minutes 90 to 115 | The tool server or its wiring will not work | Call the builder from its script and carry the saved change forward. |
| Minutes 115 to 160 | The gate says it could not judge | The presenter shows a recorded ACCEPT and REJECT, labeled as recorded. |
| Minutes 160 to 175 | Anything | Voice goes first. |

## Test evidence: what was observed, by whom, and what is still open

These are peer-reported observations from the workshop team's test codespaces. The retained logs are held by the team and available on request. None of them is an unaided attendee run.

| What | Revision and platform | Observation | Still open |
|---|---|---|---|
| Mantle first win, cold | Source `81dc3efa`, Linux codespace, 4 cores and 16 GiB, no prebuild, tester account, automated browser (Nov 2) | Codespace requested 04:03:16Z, setup finished 04:09:36Z, install and train 27 seconds, working restart confirmation 04:13:44Z, 10 minutes 28 seconds from opening. All four checks behaved. | A fresh account, an unaided person, and a different room network |
| Mantle, second cold codespace | Source `1282548e`, Linux codespace, 4 cores and 16 GiB, no prebuild, existing account, automated browser (Nov 2, opening 06:04:24Z) | Full restart confirmation 11 minutes 52 seconds after opening, REBOOT after consent, reset clarified, factory reset answered with the exact refusal and person offer in all three tested positions (followed by an unwanted long resume paragraph). A later change, tested on the same machine with a fresh agent and no new full cold run, replaced it with the short question "Do you want to carry on with your router restart, or leave it?" in the clarification case. After the first message or after a restart, the engine can still add its normal follow-up question, so the refusal is not the only text in those positions. | A fresh account, an unaided person, and the unchanged latest pack |
| Mantle tool calls | Source `81dc3efa`, the earlier codespace of the first row (opened about 04:03Z) | Expanded event cards: one sent `REBOOT` after consent, none after a denial or for reset requests, and no router was contacted (mock tool) | A real device |
| First check | Mac, Python only | Passed on the Mantle tool file. The tests pass. | A run-time trace |
| Gate | Mac, Python only | Seven tests pass: ACCEPT for the good change, REJECT by name for each bad one, no file written by a change that tries | Linux, and a change written through the tool server on a workshop key (one existing-key builder file was accepted, see the builder row) |
| Chapter 6 gate on Linux | Linux codespace, then a real run on the team's own test machine | Wrapper proven, 11 of 11 isolation tests, 5 gate tests OK, good ACCEPT, ignores-limit REJECT. The workshop lead reported that a later real gate run also passed. The router helper's gate then ran on Linux in a test codespace and returned ACCEPT for a freshly built file (next rows). | The router helper's gate on the four candidate files, run on Linux by someone following the pack |
| Tool server behavior | Mac, Python only, stand-ins and no key | Cancel and one-build-at-a-time behavior passes 2 tests | Anything with a real key |
| Builder, live key, first run | Existing key, run through `builder.py` alone, not the tool server (platform not recorded in this sheet) | One run took 27.5 seconds and produced a 114-byte file that the gate judged ACCEPT. | Not through the tool server |
| Builder, live key, first whole chain | Source `6f2bf1fc`, the cold 4-core machine, existing authorized key, one paid run (Nov 2, 07:00Z) | Mantle called the tool server, which started a real Agents session that returned in 30.5 seconds and saved a 114-byte file. The unchanged gate judged it ACCEPT. The file was not run or applied. The helper's reply did not show the build id, path, or hash, so this was not a pass. | Fixed afterwards (next rows) |
| Builder through Mantle, second run | Source `e0a6513f`, same machine, one paid run (08:38Z) | The build finished in about 25 seconds, but Mantle stopped the tool after its default 10 seconds and told the customer to retry. The saved 160-byte file returned an "unknown" answer, because the free-form request replaced the task and the build lost the required return value. The unchanged gate REJECTED it. | Fixed afterwards (next row) |
| Builder through Mantle, repaired | Source `00d6f4d9`, same machine, third and last paid run (08:52Z) | From the customer's message to the helper's reply took 28.2 seconds. The reply showed the real build id, an absolute path, and the full sha256, with no timeout. The file was 114 bytes with the expected return value, and the unchanged gate returned ACCEPT from a different folder. Nothing was run or applied. The three paid runs allowed are spent. Cost was not returned. | A new build on the latest text, a cold run, an unaided attendee, and cost |

## Appendix: what the room needs

- Each person brings their own free Rasa Developer Edition key and their own OpenAI key, saved as Codespaces secrets named `RASA_LICENSE` and `OPENAI_API_KEY`, selected for this repository. The Developer key cannot be shared. The OpenAI key needs the Agents API permissions listed above.
- The codespace can show as available while the Mantle install is still running. Wait for the setup to print its finished line.
- The codespace opens in the workshop folder. Use absolute paths for helper scripts: `/workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/`.
- Never paste a key into a command, a file, or a chat. If a step prints an error, copy the words and not the keys, and ask for help early. Each block stands on the one before it.
