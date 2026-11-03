# Your builder, behind the router helper

This runs in the workshop codespace. Follow [`ATTENDEE-PACK.md`](../../ATTENDEE-PACK.md) for the exact steps. This page explains the pieces. The default practice mode adds `--fixture` to `builder_server.py` (and to `builder.py` if you run it alone).
They copy the public `gate/candidates/good.py` example into a new output folder instead of calling the Agents API.
The terminal and helper label the result **Fixture build** and say that no Agents session started.
This checks file handling, MCP transport, the visible receipt and the gate; it does not test code generation.
Mantle's own model calls still use your OpenAI key and can incur charges. Omit `--fixture` only when you intend a live, billed build.

1. The codespace image already prepared the locked builder environment at `~/.venv-builder` (openai 3.42.1 and mcp 1.28.1). Nothing to install.
2. For the practice route you need no extra permissions. For one optional billed build, your OpenAI key (the `OPENAI_API_KEY` Codespaces secret) needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write`. Never paste it into a file or a command.
3. Start the tool server in its own terminal and leave it running: `~/.venv-builder/bin/python builder_server.py --fixture`. For the optional billed build, restart it without `--fixture`. Each build writes to its own folder, `scratch/build-<id>/check_line_status.py` next to `builder.py`, and returns the file's absolute path and sha256. Use that exact path.
4. To run one build without the helper, use `~/.venv-builder/bin/python builder.py --fixture` (or without `--fixture` for a billed build) and watch the session's events. Edit `INSTRUCTIONS` in `builder.py` first if you want to change the task.

**Mantle path.** Install the skill with `~/.venv-mantle/bin/python change_builder/install_change_builder.py ~/router-helper-agent` (use your agent's folder), then `~/.venv-mantle/bin/rasa train` and `~/.venv-mantle/bin/rasa inspect --port 5010` from your agent's folder. The installer copies `change_builder` into `skills/` and raises `tool_timeout` in `agent.yml` to at least 450 seconds, because Mantle stops a custom tool after 10 seconds by default and the tool waits up to 360 for the builder. No `integrations.yml` entry is needed. The skill's tool calls the tool server for you and sends the customer the build id, whether a file was saved, the file's path, and its sha256, straight from the server's answer. The model does not reword them. Ask the helper for a change, for example "add a check that tells me the line status". The builder's fixed instructions decide the function and its return value, so the request only describes why the change is wanted. Keep `builder_server.py` running in the second terminal. If the helper says it cannot tell whether a build started, look at the server's terminal before asking again. Only the busy refusal says "No build started".


What has been run, by testers on November 2 (not by anyone following this page): the practice builder, tool server, skill and gate ran end to end in a fresh test codespace with no billed Agents session. One billed build through the tool server, on earlier code with a real key (the repaired run, third of three billed test runs, listed in `archive/2026-11-02-before-new-york/RUN-SHEET-EVIDENCE-TABLE.md`), took 28.2 seconds from the customer's message to the helper's reply, which showed the build id, an absolute path and the sha256; the saved file was 114 bytes and the unchanged gate returned `ACCEPT` from a different folder. The cost was not returned. The refreshed head has not had its own cold run yet. `change_builder`'s message formatting is also tested with stand-ins (`change_builder/test_change_builder.py`). A real builder session can take minutes, and Mantle's default tool timeout is 10 seconds, which is why the skill waits up to 360 seconds itself and the installer raises the tool wait to at least 450.

The tool server keeps a build "running" until its worker really finishes, even if the caller cancels. A second request
meanwhile is refused. Each build writes to its own folder under `scratch/` and returns its build id and the sha256 of
the file. The builder stops waiting for new events once `BUILDER_MAX_SECONDS` (300) have passed. That is not a hard limit on the whole build: the check happens when an event arrives, so the last event can take up to 120 more seconds (the request timeout), and the artifact list and download come after the check. Closing the stream does not confirm that OpenAI ended the hosted session. Mantle waits 360 seconds. Those two behaviors
are tested with stand-ins and no key in `test_builder_server.py`.

## Optional appendix: on your own machine

Not part of the workshop. Outside a codespace, create your own environment with `openai==3.42.1` and `mcp==1.28.1` (the versions the codespace lock pins), and use your own Rasa Pro environment for the skill installer, `rasa train` and `rasa inspect`. The tests in this folder need no key.
