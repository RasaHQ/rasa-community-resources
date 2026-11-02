# Run sheet: build a dark software factory with Rasa Mantle, Rasa Studio, and the OpenAI Agents API

sow: public

Three hours. Minutes count from the start. This sheet is for the session that uses GitHub Codespaces. It says what each person builds and sees, minute by minute. All times below are planned targets. Nobody has yet confirmed that a first-time attendee can reach them. The evidence table near the end says what was observed, by whom, and what is still open.

## The one small agent: the router restart helper

Everyone builds the same small agent. A customer says "restart my router". The helper asks them to confirm, then records a restart command and nothing else. It never records a factory reset, which would erase the customer's Wi-Fi name and password. The workshop simulates the command. It does not contact a router or change anyone's internet connection.

Why this agent:

- It is small enough to build on either path in a short time.
- It has one real risk: a restart and a factory reset sound alike and do very different things. That makes the value easy to see (a confirmation, then the right command) and gives the later blocks something to check.
- A public exercise and a Mantle example already exist for the same situation (the router-support example in this repository).

You can tell it works when:

1. "Restart my router" makes the helper ask you to confirm.
2. "Yes" makes it record one command, `REBOOT`.
3. "Reset it" makes it ask which one you mean, and it sends nothing until you answer.
4. A request for a factory reset makes it say it cannot do that here and offer help from a person. It records no factory-reset command.

## Two paths to the same result

- **Mantle path:** the Mantle Inspector, a skill file, a tool, and an installer script that makes a fresh Mantle agent into the helper.
- **Studio path:** Rasa Studio's visual builder. You import a ready-made restart flow that Studio itself exported, change one thing, train, and try it. You build the reset flow by hand afterward.

The routes differ in what they reach by minute 30 (see the schedule). Then you do the other path, compare, and the rest of the session grows the helper into a station on a dark software factory.

## At a glance (planned targets)

| Minutes | Block | You build | You see | Target result |
|---|---|---|---|---|
| 0 to 10 | The result | Nothing yet. Everyone opens a codespace | The finished helper handling the four checks above | You know what "working" means |
| 10 to 30 | First path | Mantle: install, train, inspect. Studio: import, edit one wording, train | Your helper asking to confirm and recording `REBOOT` | Mantle: all four checks. Studio: the first two checks |
| 30 to 50 | The other path, and compare | The other path. On Studio, the reset flow by hand | The same checks on both, and the files each path keeps | All four checks on both paths |
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

## Minutes 10 to 30: the first path

**Mantle path.** In a new folder, run `rasa init --engine mantle --no-prompt`, then the installer `router-helper/mantle/install_helper.py` on that folder, then `rasa train`, then `rasa inspect --port 5010`, and open the Inspector address. The installer moves the starter banking skills out of the active skills and sets a router-only persona and rules. Then run the four checks.

**Studio path.** Studio starts in the background when the codespace starts. When `studio-status.sh` says it is ready, run `router-helper/studio/import-restart-flow.sh`. It uploads the restart flow that Studio exported. Open the assistant, edit the confirmation wording through **Edit response**, train with Draft selected, try it, and run the first two checks.

You build: the helper on one path.
You see: the confirmation, then `REBOOT` recorded.
Target at minute 30: Mantle shows all four checks. Studio shows the imported, edited restart flow working (the first two checks).

The exact steps are in the attendee pack. The files for both paths are in `router-helper/`.

## Minutes 30 to 50: the other path, and compare

Do the path you did not take. On Studio, build the reset flow by hand (step 6 of `router-helper/studio/STEPS.md`) and run the last two checks. Then put the two side by side with these questions:

- Which one asked you to confirm, and who wrote the confirmation, you or the engine?
- Where is the command `REBOOT` stored on each path?
- What does each path keep as files?

**What Studio exports and how it connects** (from Rasa's Studio tutorial and compatibility pages, read Nov 2):

- `rasa studio download` writes the assistant to files: flows (`data/studio_flows.yml`), language data (`data/studio_nlu.yml`), the domain, and, from Rasa Pro 3.9.8, the config and endpoints.
- Some things are done only in files after the download: tracing, an interactive voice response (IVR) channel, end-to-end tests, secrets management, personally identifiable information (PII) management, markers, custom information retrieval, conversation tracking, and the generation prompt in `flows.yml`.
- A Studio assistant reaches other systems through a custom action endpoint (Assistant Settings, Action Endpoint), or, after a download, through a Model Context Protocol (MCP) server in `endpoints.yml` and a flow `call` step with `mcp_server`. Rasa lists MCP servers as a beta feature since Rasa 3.14.
- Rasa's Mantle changelog says Studio trains and runs a Mantle assistant and that Copilot refers to Studio. Rasa's Studio changelog and compatibility matrix do not mention Mantle, and the Studio build we tested pairs with an older Rasa Pro. Whether the Studio build in the room shows a Mantle agent is not yet shown.

Target at minute 50: two paths, one result.

## Minutes 50 to 70: the source-file check

The helper must never record `FACTORY_RESET` when asked to restart. A check can look at the configured restart command in a file instead of at what the helper said.

Run `router-helper/check_helper.py` on the Mantle tool file, or on a downloaded Studio flows file. It reads the configured command and fails if it is not `REBOOT`. Then change the file to `FACTORY_RESET` and run the check again. It fails, and names why.

You build: a source-file check.
You see: the check pass, then fail on the wrong command, even though the helper's reply could still sound right.
Target at minute 70: a check that reads the configured command, not the reply.

This is a source-file check of the configured restart command. It does not watch a live conversation, so a pass does not prove the helper ran that command at run time. It exits 2 when it cannot find a command, so a missing command is never a pass. If every check passes by minute 70, people who leave then have a working helper on both paths and a check for it.

## Minutes 75 to 115: the factory begins, with the OpenAI Agents API

Now the helper becomes the front desk of a factory. The factory's builder is an agent you create with the OpenAI Agents API, using your own key.

**Minutes 75 to 90: create your builder.** You choose the model and write its instructions, run a session, and watch the stream of events. The task is a small change to the helper: add one read-only operation, "check line status". The agent works in OpenAI's hosted sandbox and reports what it wrote.

Facts from OpenAI's Agents API quickstart (read Nov 2): your key needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write`. A session starts with `client.beta.agents.sessions.create(...)`. An agent is a model, instructions, tools, and optional MCP servers. Model use is billed at the model's API rates.

**Minutes 90 to 115: put the builder behind the helper.** A small tool server wraps your builder. On the Mantle path, add it as an MCP server in `integrations.yml` and import its tool into the skill. On the Studio path, download the assistant, add the same server to `endpoints.yml`, and add a flow step that calls its tool.

You build: your builder agent, and the connection to it.
You see: the session's events, then the helper calling your builder and showing the proposed change.
Target at minute 115: a request goes in and a proposed change comes out.

The code is in `router-helper/builder/`: `builder.py` (your agent, with the instructions you edit) and `builder_server.py` (the tool server), with a README for the Mantle and Studio wiring. On the Studio path, Studio's own chat cannot reach this server, so the Studio route runs the downloaded project from files.

## Minutes 115 to 140: the gate

Run the gate on your builder's change. Then run it on a deliberately bad change that records `FACTORY_RESET`. The gate names the test that rejected it, and neither the builder nor the helper can edit it.

You see: one ACCEPT, one REJECT, and the name of the failing test.
Target at minute 140: a line that can say no.

The gate is `router-helper/gate/gate.py`, with a good change and three bad ones in `router-helper/gate/candidates/`. It accepts only a file that holds one function, `check_line_status()`, with no arguments and one statement: a return of a dictionary written out as plain values. It reads the file once and judges those bytes. It never runs the change, so a change cannot write a file or open the network while it is judged. This fits one small read-only operation and is not a general sandbox.

## Minutes 140 to 160: release

Run the whole line once: ask the helper for the change, let the builder propose it, let the gate judge it, then approve or refuse as the person at the last gate. Record your decision.

Target at minute 160: one change built, checked, and released or refused by you.

## Minutes 160 to 175: voice (drop first)

Switch speech on for the Mantle helper. Mantle's docs list the speech providers and their keys, which attendees may not have. Drop this block if time is short.

## Minutes 175 to 180: close

Show the line again with the pieces each person built. Name the one check each person could not edit. Hand out the recap.

## If a station fails: the fallback at each stage

| Stage | If this breaks | Fall back to |
|---|---|---|
| Minutes 0 to 30 | A codespace will not open or the setup stalls | Pair with a neighbor who has one. The presenter keeps one working codespace for the room. |
| Minutes 0 to 30 | Your key or license is rejected | Say so at once. Watch your neighbor's path until a key is fixed. Never retry a key that was rejected. |
| Minutes 10 to 50 | One path will not work | Try the other path. If both paths fail, follow the presenter's demonstrated or recorded example, and note which parts you could not complete. |
| Minutes 50 to 70 | The check cannot find a command | Read the exit code. 2 means it found nothing, and the file layout is the first thing to look at. |
| Minutes 75 to 115 | Your Agents API session fails (permissions, quota, model) | The presenter runs one builder on the screen. You watch its events and take the saved change in `router-helper/gate/candidates/good.py` to the next block. |
| Minutes 90 to 115 | The tool server or its wiring will not work | Call the builder from its script and carry the saved change forward. |
| Minutes 115 to 160 | The gate says it could not judge | The presenter shows a recorded ACCEPT and REJECT, labeled as recorded. |
| Minutes 160 to 175 | Anything | Voice goes first. |

## Test evidence: what was observed, by whom, and what is still open

These are peer-reported observations from the workshop team's test codespaces. The retained logs are held by the team and available on request. None of them is an unaided attendee run.

| What | Revision and platform | Observation | Still open |
|---|---|---|---|
| Mantle first win, cold | Source `81dc3efa`, Linux codespace, 4 CPU and 16 GiB, no prebuild, tester account, automated browser (Nov 2) | Codespace requested 04:03:16Z, setup finished 04:09:36Z, install and train 27 seconds, working restart confirmation 04:13:44Z, 10 minutes 28 seconds from opening. All four checks behaved. | A fresh account, an unaided person, and a different room network |
| Mantle tool calls | Same run | Expanded event cards: one sent `REBOOT` after consent, none after a denial or for reset requests, and no router was contacted (mock tool) | A real device |
| Studio start, cold | Same codespace, Studio 1.15.2, model service 3.15.8 | Launcher healthy at 04:19:18Z, 16 minutes 02 seconds from opening | The background start in the final design, timed |
| Studio authoring by hand | Same run, manual launch | Restart-only flow saved at 04:43:35Z after QA tooling errors. This missed minute 30. | Not a learner number |
| Studio import | Studio 1.15.2, Mantle environment CLI 3.21.0.dev5, warm | Configuration, login, and upload succeeded, 11.8 seconds for the CLI. The import script, unmodified, then finished in 33 seconds on a healthy licensed 4-core Studio (configuration at 10.6 seconds, login at 20.3, upload at 31.8). The imported assistant exists and shows the restart flow. | Cold start of this exact design with a new account, and an unaided person. The warm end-to-end run (import script, wording edit that survived a reload, training with Draft selected in 37 seconds, then a chat showing the edited confirmation and the exact REBOOT acknowledgement) passed on a healthy licensed 4-core Studio. |
| Studio trained export | Studio 1.15.2 and model service 3.15.8 | The exported restart flow trained in 38 seconds, and chat confirmed and recorded `REBOOT` | The same on the imported copy |
| First check | Mac, Python only | Passed on the real Studio export and on the Mantle tool file. Five tests pass. | An attendee's downloaded export, and a run-time trace |
| Gate | Mac, Python only | Seven tests pass: ACCEPT for the good change, REJECT by name for each bad one, no file written by a change that tries | A change a real builder wrote, and Linux |
| Chapter 6 gate on Linux | Linux codespace, operator run | Wrapper proven, 11 of 11 isolation tests, 5 gate tests OK, good ACCEPT, ignores-limit REJECT | The router helper's gate on Linux |
| Builder and tool server | Mac, with stand-ins and no key | The tool server's cancel and one-build-at-a-time behavior passes 2 tests. A builder run on an existing key took 27.5 seconds and produced a 114-byte file that the gate accepted. | A run on a workshop key through the tool server, and the Mantle and Studio wiring |

## Appendix: what the room needs

- Each person brings their own free Rasa Developer Edition key and their own OpenAI key, saved as Codespaces secrets named `RASA_LICENSE` and `OPENAI_API_KEY`, selected for this repository. The Developer key cannot be shared. The OpenAI key needs the Agents API permissions listed above.
- Studio is hands-on. It needs a license with a Studio entitlement, saved as the Codespaces secret `RASA_STUDIO_LICENSE`. The free Developer key did not unlock Studio in testing. Rasa will provide the Studio keys.
- Studio runs from the Docker setup in `.devcontainer/software-factories-workshop/start-studio.sh`, inside the codespace, and needs a codespace with at least 4 cores. It starts by itself in the background.
- The codespace can show as available while the Mantle install is still running. Wait for the setup to print its finished line.
- The codespace opens in the workshop folder. Use absolute paths for helper scripts: `/workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/`.
- Never paste a key into a command, a file, or a chat. If a step prints an error, copy the words and not the keys, and ask for help early. Each block stands on the one before it.
