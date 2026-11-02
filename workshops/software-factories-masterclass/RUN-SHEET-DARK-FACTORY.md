# Run sheet: build a dark software factory with Rasa Mantle, Rasa Studio, and the OpenAI Agents API

sow: public

Three hours. Minutes count from the start. This sheet is for the session that uses GitHub Codespaces. It says what each person builds and sees, minute by minute. Setup details are in the short appendix at the end.

## The one small agent: the router restart helper

Everyone builds the same small agent. A customer says "restart my router". The helper asks them to confirm, then sends a restart and nothing else. It never sends a factory reset, which would erase the customer's Wi-Fi name and password.

Why this agent:

- It is small enough to build in under 30 minutes on either path.
- It has a real risk in one place: a restart and a factory reset sound alike and do very different things. That makes the value easy to see (a confirmation, then the right command) and gives the later blocks something to check.
- A public exercise and a Mantle example already exist for the same situation (the router-support example in this repository), so the second half of the session has tested material to grow from.

The result is the same on both paths. You can tell it works when:

1. "Restart my router" makes the helper ask you to confirm.
2. "Yes" makes it record one command, `REBOOT`.
3. "Reset it" makes it ask which one you mean, and it sends nothing until you answer.
4. It never records `FACTORY_RESET` unless you ask for a factory reset in your own words and confirm that too.

## Two paths to the same result

- **Mantle path:** the Mantle Inspector, a skill file, a tool, and your coding agent or editor.
- **Studio path:** Rasa Studio's visual builder, with flows, slots, and a confirm step.

You work on whichever path you pick, side by side with a neighbor on the other if you like. By minute 30 the helper works on either path. Then you build the other path, compare, and the rest of the session grows the helper into a station on a dark software factory.

## At a glance

| Minutes | Block | You build | You see | Complete result |
|---|---|---|---|---|
| 0 to 10 | The result | Nothing yet | The finished helper handling the four checks above | You know what "working" means |
| 10 to 30 | Build the helper, your path | The router restart helper on Mantle or in Studio | Your helper asking to confirm and recording `REBOOT` | A working helper by minute 30 |
| 30 to 50 | Build it the other way, then compare | The same helper on the other path | The same four checks passing on both, and the files each path keeps | Two paths, one result |
| 50 to 70 | First check | A check that reads the command the helper records | The check passing, then failing when the restart is wired to a factory reset | A check the helper cannot talk its way past |
| 70 to 75 | Break | | | |
| 75 to 90 | The factory begins: your builder | An OpenAI Agents API agent that you create, with your own key | Its session stream, and the change it writes in a scratch copy | Your own builder agent has proposed a change |
| 90 to 115 | The builder behind the helper | A small tool server that hands a request to your builder | The helper calling your builder from the Inspector, or from a Studio flow | A request goes in and a proposed change comes out |
| 115 to 140 | The gate | A deliberately bad change, and the protected check run on both | One change accepted, one rejected, and the name of the test that rejected it | A line that can say no |
| 140 to 160 | Release | The final human gate and a decision record | You approving or refusing one change | The line run once, end to end |
| 160 to 175 | Voice (drop first if time is short) | Speech switched on for the Mantle helper | The same helper answering by voice | Voice on the same helper |
| 175 to 180 | Close | Nothing | The line with your pieces on it | A take-home recap |

If time is short, drop voice first. Then shorten the release block. Never shorten the first 30 minutes.

## Minutes 0 to 10: the result

Say: "In 30 minutes you will have a small agent that handles one risky request safely. After that we turn it into a station on a dark software factory. That is a production line where nobody reads each change as it passes. Agents do the work. Checks that the agents cannot edit decide what moves on. A person stands at a few defined gates."

Show: the finished helper, once, handling the four checks above. No other demo.

**Everyone opens their codespace now, at minute 0, while the result is on the screen.** In tests the setup took 5 to 6 minutes, and a first reply came 7 to 9 minutes after the codespace was created. Wait for the setup to print its finished line before you start building at minute 10 to 15.

## Minutes 10 to 30: build the helper on your path

**Mantle path.**

1. In a new folder in the codespace, run `rasa init --engine mantle --no-prompt`, then `rasa inspect --port 5010`, and open the Inspector address.
2. Add a skill for the helper. The finished router-support skill in `examples/mantle-text-telco-diagnostics-gpt/skills/connectivity_recovery/` is the model: it keeps a restart and a factory reset apart, asks the customer which one they mean when they only say "reset", and uses a confirmation the engine asks for before the device command is sent.
3. Talk to it and run the four checks.

**Studio path.**

1. Sign in to Studio with your account and create an assistant project.
2. Create a flow named "restart router": a start step, a collect step for "confirm restart" (yes or no) with a description that says what is being confirmed, a condition on the answer, a set-slot step that sets `command_sent` to `REBOOT` on yes, and a message that says a restart was sent and the Wi-Fi name and password are kept. On no, a message that nothing was sent.
3. Train and try it in the chat, and run the four checks.

You build: the helper.
You see: the confirmation, then `REBOOT` recorded.
Complete at minute 30: your helper passes the four checks on your path.

Files for both paths are in `router-helper/`: the Mantle skill, its tool and responses in `router-helper/mantle/skills/router_restart/`, and the Studio steps in `router-helper/studio/STEPS.md`.

Proof so far: a Mantle agent answered in the Inspector in clean 4-core and 8-core codespaces, about 7 to 9 minutes after creation (one run each). A tester signed in to Studio and created an assistant. The router helper itself has not been run on either path yet. The Mantle files follow Rasa's docs and have not been trained. The Studio steps have not been clicked through. Do not promise the 30-minute result until a person has done it.

## Minutes 30 to 50: the other path, and compare

Build the helper on the path you did not take. Then put the two side by side with these questions:

- Which one asked you to confirm, and who wrote the confirmation, you or the engine?
- Where is the command `REBOOT` stored on each path?
- What does each path keep as files?

**What Studio exports and how it connects** (from Rasa's Studio tutorial and compatibility pages, read Nov 2):

- `rasa studio download` writes the assistant to files: flows (`data/studio_flows.yml`), language data (`data/studio_nlu.yml`), the domain, and, from Rasa Pro 3.9.8, the config and endpoints.
- Some things are done only in files after the download: tracing, an IVR channel, end-to-end tests, secrets management, PII management, markers, custom information retrieval, conversation tracking, and the generation prompt in `flows.yml`.
- A Studio assistant reaches other systems through a custom action endpoint (Assistant Settings, Action Endpoint), or, after a download, through an MCP server in `endpoints.yml` and a flow `call` step with `mcp_server`. Rasa lists MCP servers as a beta feature since Rasa 3.14.
- Rasa's Mantle changelog says Studio trains and runs a Mantle assistant and that Copilot refers to Studio. Rasa's Studio changelog and compatibility matrix do not mention Mantle, and the Studio build we tested pairs with an older Rasa Pro. Whether the Studio build in the room shows a Mantle agent is not yet shown.

Complete at minute 50: two paths, one result.

## Minutes 50 to 70: the first check

The helper must never send `FACTORY_RESET` when asked to restart. A check can look at the command that was recorded, not at what the helper said.

**Both paths.** Run a small check that reads the command the helper records for a restart and fails if it is not `REBOOT`. Then change the restart so it records `FACTORY_RESET` and run the check again. It fails, and names why.

You build: a check.
You see: the check pass, then fail on the wrong command, even though the helper's reply still sounds right.
Complete at minute 70: a check the helper cannot talk its way past.

The check is `router-helper/check_helper.py`. It reads the command the helper records, from the Mantle tool file or from the downloaded Studio flows file, and exits 2 when it cannot find one so a missing command is never a pass. Its tests pass with Python alone. It has not been run against a real Studio export, whose file layout is not yet confirmed.

People who leave at minute 70 have a working helper on both paths and a check for it.

## Minutes 75 to 115: the factory begins, with the OpenAI Agents API

Now the helper becomes the front desk of a factory. The factory's builder is an agent you create with the OpenAI Agents API, using your own key.

**Minutes 75 to 90: create your builder.** You choose the model and write its instructions, run a session, and watch the stream of events. The task is a small change to the helper: add one read-only operation, "check line status". The agent works in OpenAI's hosted sandbox and reports what it wrote.

Facts from OpenAI's Agents API quickstart (read Nov 2): your key needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write`. A session starts with `client.beta.agents.sessions.create(...)`. An agent is a model, instructions, tools, and optional MCP servers. Model use is billed at the model's API rates.

**Minutes 90 to 115: put the builder behind the helper.** A small tool server wraps your builder. On the Mantle path, add it as an MCP server in `integrations.yml` and import its tool into the skill. On the Studio path, download the assistant, add the same server to `endpoints.yml`, and add a flow step that calls its tool (or use the custom action endpoint).

You build: your builder agent, and the connection to it.
You see: the session's events, then the helper calling your builder and showing the proposed change.
Complete at minute 115: a request goes in and a proposed change comes out.

The code is in `router-helper/builder/`: `builder.py` (your agent, with the instructions you edit) and `builder_server.py` (the tool server), with a README for the Mantle and Studio wiring.

Proof so far: nothing here has been run by anyone for this workshop on a workshop key. The code follows OpenAI's Agents API quickstart and its page on files, and Rasa's MCP docs. The existing live builder (chapter 5 of the book) runs the same kind of session, and its protected path is macOS only.

## Minutes 115 to 140: the gate

Run the protected check on your builder's change. Then run it on a deliberately bad change that records `FACTORY_RESET`. The check names the test that rejected it, and neither the builder nor the helper can edit it.

You see: one ACCEPT, one REJECT, and the name of the failing test.
Complete at minute 140: a line that can say no.

The gate is `router-helper/gate/gate.py`, with a good change and two bad ones in `router-helper/gate/candidates/`. It refuses a change that imports the network or process modules, names a restart or factory-reset command, or returns the wrong answer, and it runs the change under a no-network wrapper that was proven by behavior and checked against its pinned hash before use. It prints the name of the test that rejected a change and exits 2, judging nothing, when it cannot prove the wrapper.

Proof so far: the gate's five tests pass on a Mac, including ACCEPT for the good change, REJECT by name for each bad one, and no judgment when the isolation helper has been edited. It has not been run on Linux or on a change that a real builder wrote. The Linux path for the chapter 6 gate has passed its refusal tests on macOS and Linux.

## Minutes 140 to 160: release

Run the whole line once: ask the helper for the change, let the builder propose it, let the gate judge it, then approve or refuse as the person at the last gate. Record your decision.

Complete at minute 160: one change built, checked, and released or refused by you.

## Minutes 160 to 175: voice (drop first)

Switch speech on for the Mantle helper. Mantle's docs list the speech providers and their keys, which attendees may not have. Drop this block if time is short.

## Minutes 175 to 180: close

Show the line again with the pieces each person built. Name the one check each person could not edit. Hand out the recap.

## If a station fails: the fallback at each stage

| Stage | If this breaks | Fall back to |
|---|---|---|
| Minutes 0 to 30 | A codespace will not open or the setup stalls | Pair with a neighbor who has one. The presenter keeps one working codespace for the room. |
| Minutes 0 to 30 | Your key or licence is rejected | Say so at once. Watch your neighbor's path until a key is fixed. Never retry a key that was rejected. |
| Minutes 10 to 50 | One path will not work | Build the other path, and compare on the presenter's screen. Both must not fail together, because they use different keys. |
| Minutes 50 to 70 | The check cannot find a command | Read the exit code. 2 means it found nothing, and the file layout is the first thing to look at. |
| Minutes 75 to 115 | Your Agents API session fails (permissions, quota, model) | The presenter runs one builder on the screen. You watch its events and take the saved change in `router-helper/gate/candidates/good.py` to the next block. |
| Minutes 90 to 115 | The tool server or its wiring will not work | Call the builder from its script and carry the saved change forward. |
| Minutes 115 to 160 | The gate says it could not judge | That is the gate refusing to run unprotected. The presenter shows a recorded ACCEPT and REJECT, labelled as recorded. |
| Minutes 160 to 175 | Anything | Voice goes first. |

## Appendix: what the room needs

- Each person brings their own free Rasa Developer Edition key and their own OpenAI key, saved as Codespaces secrets named `RASA_LICENSE` and `OPENAI_API_KEY`, selected for this repository. The Developer key cannot be shared. The OpenAI key needs the Agents API permissions listed above.
- Studio is hands-on. It needs a licence with a Studio entitlement, saved as the Codespaces secret `RASA_STUDIO_LICENSE`. The free Developer key did not unlock Studio in testing. Rasa will provide the Studio keys.
- Studio runs from the Docker setup in `.devcontainer/software-factories-workshop/start-studio.sh`, inside the codespace, and needs a codespace with at least 4 cores. It started with all required services healthy in about 1 to 1.5 minutes on a warm 8-core codespace. A first start on a loaded machine took longer than an earlier health budget, which has since been lengthened.
- The codespace can show as available while the Mantle install is still running. Wait for the setup to print its finished line.
- The codespace opens in the workshop folder. Use absolute paths for helper scripts: `/workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/`.
- Never paste a key into a command, a file, or a chat. If a step prints an error, copy the words and not the keys, and ask for help early. Each block stands on the one before it.
