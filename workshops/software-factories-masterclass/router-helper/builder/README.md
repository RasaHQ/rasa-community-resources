# Your builder, behind the router helper

For a local rehearsal, add `--fixture` to both `builder.py` and `builder_server.py`.
They copy the public `gate/candidates/good.py` example into a new output folder instead of calling the Agents API.
The terminal and helper label the result **Fixture build** and say that no Agents session started.
This checks file handling, MCP transport, the visible receipt and the gate; it does not test code generation.
Mantle's own model calls still use your OpenAI key and can incur charges. Omit `--fixture` only when you intend a live, billed build.

1. Make a virtual environment and install: `python3 -m venv ~/.venv-builder && ~/.venv-builder/bin/pip install --upgrade openai mcp==1.28.1`.
2. Your OpenAI key (the `OPENAI_API_KEY` Codespaces secret) needs the permissions `api.agents.read`,
   `api.agents.write`, and `api.responses.write`. Never paste it into a file or a command.
3. Edit `INSTRUCTIONS` in `builder.py`, then run `~/.venv-builder/bin/python builder.py`. Watch the session's
   events. Each build writes to its own folder, `scratch/build-<id>/check_line_status.py` next to `builder.py`, and prints the file's absolute path and sha256. Use that exact path.
4. Start the tool server in a second terminal: `~/.venv-builder/bin/python builder_server.py`.

**Mantle path.** Install the skill with `python3 change_builder/install_change_builder.py ~/router-helper-agent` (use your agent's folder), then `rasa train` and `rasa inspect --port 5010`. The installer copies `change_builder` into `skills/` and raises `tool_timeout` in `agent.yml` to at least 450 seconds, because Mantle stops a custom tool after 10 seconds by default and the tool waits up to 360 for the builder. No `integrations.yml` entry is needed. The skill's tool calls the tool server for you and sends the customer the build id, whether a file was saved, the file's path, and its sha256, straight from the server's answer. The model does not reword them. Ask the helper for a change, for example "add a check that tells me the line status". The builder's fixed instructions decide the function and its return value, so the request only describes why the change is wanted. Keep `builder_server.py` running in the second terminal. If the helper says it cannot tell whether a build started, look at the server's terminal before asking again. Only the busy refusal says "No build started".


What has been run, by a test seat on Nov 2 (not by anyone following this page): the builder on a real key saved a 114-byte file that the gate accepted, and the helper's reply shown from a recorded real result, with no new paid call. `change_builder`'s message formatting is also tested with stand-ins (`change_builder/test_change_builder.py`). Not yet proven: the whole chain from one helper request to a new real build and its reply, and the absolute path from a live build. A real builder session can take minutes, and Mantle's default tool timeout is 10 seconds, which is why the skill waits up to 360 seconds itself.

The tool server keeps a build "running" until its worker really finishes, even if the caller cancels. A second request
meanwhile is refused. Each build writes to its own folder under `scratch/` and returns its build id and the sha256 of
the file. The builder stops waiting for new events once `BUILDER_MAX_SECONDS` (300) have passed. That is not a hard limit on the whole build: the check happens when an event arrives, so the last event can take up to 120 more seconds (the request timeout), and the artifact list and download come after the check. Closing the stream does not confirm that OpenAI ended the hosted session. Mantle waits 360 seconds. Those two behaviors
are tested with stand-ins and no key in `test_builder_server.py`.
