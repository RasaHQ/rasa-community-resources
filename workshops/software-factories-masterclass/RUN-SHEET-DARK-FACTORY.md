# Run sheet: build a dark software factory with Rasa Mantle and the OpenAI Agents API

Three hours, Tuesday, November 3, 3:00 to 6:00 PM New York time. Minutes count from the start, so minute 0 is 3:00 PM and minute 180 is 6:00 PM. The slides are in `slides/` and the notes for each are in `slides/PRESENTER-NOTES.md`. This sheet is for the session that uses GitHub Codespaces. It says what each person builds and sees, minute by minute. All times below are planned targets. Nobody has yet confirmed that a first-time attendee can reach them. The evidence table near the end says what was observed, by whom, and what is still open.

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

| Minutes (clock) | Block | You build | You see | Target result |
|---|---|---|---|---|
| 0 to 10 (3:00) | The result | Nothing yet. Everyone opens a codespace | The finished helper handling the four checks above | You know what "working" means |
| 10 to 30 (3:10) | Your router helper | Install, train, inspect | Your helper asking to confirm and recording `REBOOT` | All four checks |
| 30 to 50 (3:30) | Reset handling and your own change | Your own wording and requests against the helper | How it handles a changed mind and a reset request | The helper never records anything you did not ask for |
| 50 to 70 (3:50) | Source-file check | A check that reads the configured restart command | The check passing, then failing when the file says `FACTORY_RESET` | A check the helper's replies cannot satisfy |
| 70 to 75 (4:10) | Break | | | |
| 75 to 115 (4:15) | Connect the practice builder | A tool server and the builder skill, in the two prepared environments | The helper's reply with a Fixture build label, build id, saved path and sha256 | A request goes in and a saved file comes out. One optional billed Agents API build |
| 115 to 140 (4:55) | Check the exact proposal | The receipt check, then the gate on the saved file and the four fixed candidates | One ACCEPT, three REJECT, and the names of the failing tests | A line that can say no |
| 140 to 160 (5:20) | Record your decision | A short review note: path, hash, mode, gate results, approve or refuse | Your written decision | A human record. Nothing is installed, applied or deployed |
| 160 to 175 (5:40) | Studio 2 preview | Nothing | The presenter's own screen | Hear about the preview, then join the Rasa Community |
| 175 to 180 (5:55) | Close | Nothing | The line with your pieces on it | A take-home recap |

If time is short, shorten the Studio 2 preview first, then the release block. Never shorten the first 30 minutes.

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

Run `router-helper/check_helper.py` on the Mantle tool file. It reads the configured command and fails if it is not `REBOOT`. Then change the file to `FACTORY_RESET` and run the check again. It fails, and names why. Then restore `REBOOT` and run it again to see `PASS` before anyone retrains or restarts the Inspector: the builder block retrains the helper from that file, so a wrong command left in it would be carried forward. Keep the conversation checks and the source-file check as separate observations.

You build: a source-file check.
You see: the check pass, then fail on the wrong command, even though the helper's reply could still sound right, then pass again once `REBOOT` is restored.
Target at minute 70: a check that reads the configured command, not the reply.

This is a source-file check of the configured restart command. It does not watch a live conversation, so a pass does not prove the helper ran that command at run time. It exits 2 when it cannot find a command, so a missing command is never a pass. If every check passes by minute 70, people who leave then have a working helper and a check for it.

## Minutes 75 to 115: connect the practice builder

Now the helper becomes the front desk of a factory. The default is a practice builder. It copies the public good example into a new output folder, starts no OpenAI Agents session, and generates no new code. It lets everyone check the tool connection, the saved-file receipt and the gate in the two environments the image prepared (`~/.venv-mantle` and `~/.venv-builder`). Mantle's own conversation still uses each person's OpenAI key.

Steps, as the attendee pack shows: start the tool server with `--fixture` in its own terminal and leave it running. In a second new terminal, stop the Inspector, run the `change_builder` installer, train, and open the Inspector again. The installer copies the skill into the agent's `skills/` folder and raises Mantle's tool wait from 10 seconds to at least 450, because a live build takes minutes. Ask: `add a check that tells me the line status`. The reply carries a Fixture build label, a build id, `saved a file`, an absolute path ending in `check_line_status.py`, a sha256, and says nothing was applied to the helper.

**Optional, one billed build.** A person who wants a generated proposal restarts the tool server without `--fixture` and asks once. It takes minutes and is billed on their own key; the cost was not measured. Their key needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write` (from OpenAI's Agents API quickstart, read Nov 2). Nobody needs it to finish the default route. Practice and generated files stay labeled separately.

You build: the connection from the helper to a builder.
You see: the helper calling the builder and showing a saved-file receipt.
Target at minute 115: a request goes in and a saved file comes out.

The code is in `router-helper/builder/`: `builder.py`, `builder_server.py` and the `change_builder` skill, with a README.

## Minutes 115 to 140: check the exact proposal

Everyone checks that the saved file matches its receipt (`sha256sum --check` against the printed hash), then runs the gate on it, then on the four fixed candidates. The gate names the test that rejected each bad candidate, and neither the builder nor the helper can edit it.

You see: `OK` for the hash, one ACCEPT for the saved file and for `good.py`, and three REJECT with the names of the failing tests.
Target at minute 140: a line that can say no.

The gate is `router-helper/gate/gate.py`, with a good change and three bad ones in `router-helper/gate/candidates/`. It accepts only a file that holds one function, `check_line_status()`, with no arguments and one statement: a return of a dictionary written out as plain values. It reads the file once and judges those bytes. It never runs the change, so a change cannot write a file or open the network while it is judged. A hash match identifies bytes and a gate ACCEPT checks the finite contract. Neither is an atomic release step. This fits one small read-only operation and is not a general sandbox.

## Minutes 140 to 160: record your decision

Everyone writes a short review note: the proposal's exact path and hash, its mode (practice or generated), the gate result and control results, and approval or refusal with a reason. Nothing is installed, applied or deployed by writing the note. An operational release would need its own protected artifact and deployment procedure.

Target at minute 160: one change built, checked, and approved or refused by you, on paper.

## Minutes 160 to 175: Studio 2 preview

Say plainly that this is an early preview that attendees cannot try yet, and show it live from your own machine. Nothing in this workshop needs it and attendees do nothing. Keep keys, licenses and any command line off the shared screen, and do not say how to get the preview. Have a recording ready in case the live start fails. End with the call to action: join the Rasa Community at https://info.rasa.com/community/ to hear when Studio is released. Setup for the preview is the presenter's own and is not part of this repository.

## Minutes 175 to 180: close

Show the line again with the pieces each person built. Name the one check each person could not edit. Hand out the recap.

## Before the room opens

Open the workshop codespace on the room's network about 20 minutes before 3:00 PM and wait for `Setup finished`. Run the four checks once. Open the deck offline. Prepare the Studio 2 preview and its recording on your own machine. The full list is in `FACILITATOR.md`.

## If a station fails: the fallback at each stage

| Stage | If this breaks | Fall back to |
|---|---|---|
| Minutes 0 to 30 | A codespace will not open or the setup stalls | Pair with a neighbor who has one. The presenter keeps one working codespace for the room. |
| Minutes 0 to 30 | Your key or license is rejected | Say so at once. Watch your neighbor's path until a key is fixed. Never retry a key that was rejected. |
| Minutes 10 to 50 | The helper will not work | Pair with a neighbor whose helper works. If it still fails, follow the presenter's demonstrated or recorded example, and note which parts you could not complete. |
| Minutes 50 to 70 | The check cannot find a command | Read the exit code. 2 means it found nothing, and the file layout is the first thing to look at. |
| Minutes 75 to 115 | The optional billed build fails (permissions, quota, model) | Go back to the practice builder. Nobody needs the billed build to finish. |
| Minutes 75 to 115 | The tool server or its wiring will not work | Read the tool server terminal before asking again. Start it again with `--fixture`. If it still fails, the presenter shows a recorded receipt, labeled as recorded, and everyone takes `router-helper/gate/candidates/good.py` to the gate. |
| Minutes 115 to 140 | The gate says it could not judge | The presenter shows a recorded ACCEPT and REJECT, labeled as recorded. |
| Minutes 160 to 175 | The live preview will not start | Show the recording, or skip the preview and give the community link. |

## What was observed, and what was not

Testers ran these in fresh 4-core test codespaces on November 2, with help and an existing account. None was an unaided attendee run. The detailed table is in `archive/2026-11-02-before-new-york/RUN-SHEET-EVIDENCE-TABLE.md`.

- **The helper:** the first restart confirmation came about 10 minutes after the codespace opened, and all four rows passed by about 11 minutes.
- **The practice builder, tool server, skill and gate:** ran end to end with no billed Agents session.
- **One billed build** through the tool server on earlier code, with a real key: 28.2 seconds from the customer's message to the helper's reply, which showed the build id, an absolute path and the full sha256. The saved file was 114 bytes, and the unchanged gate returned `ACCEPT` from a different folder. The cost was not returned.
- **The gate on Linux:** ran in a test codespace and returned `ACCEPT` for a freshly built file.

Not shown: an unaided first-time attendee, a fresh account on the room's network, the cost of a build, a real router, and a cold run of the refreshed image.

## Appendix: what the room needs

- Each person brings their own free Rasa Developer Edition key and their own OpenAI key, saved as Codespaces secrets named `RASA_LICENSE` and `OPENAI_API_KEY`, selected for this repository. The Developer key cannot be shared. The OpenAI key needs the Agents API permissions listed above.
- The codespace can show as available while the Mantle install is still running. Wait for the setup to print its finished line.
- The codespace opens in the workshop folder. Use absolute paths for helper scripts: `/workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/`.
- Never paste a key into a command, a file, or a chat. If a step prints an error, copy the words and not the keys, and ask for help early. Each block stands on the one before it.
