# Your builder, behind the router helper

1. Make a virtual environment and install: `python3 -m venv ~/.venv-builder && ~/.venv-builder/bin/pip install --upgrade openai mcp==1.28.1`.
2. Your OpenAI key (the `OPENAI_API_KEY` Codespaces secret) needs the permissions `api.agents.read`,
   `api.agents.write`, and `api.responses.write`. Never paste it into a file or a command.
3. Edit `INSTRUCTIONS` in `builder.py`, then run `~/.venv-builder/bin/python builder.py`. Watch the session's
   events. Each build writes to its own folder, `scratch/build-<id>/check_line_status.py` next to `builder.py`, and prints the file's absolute path and sha256. Use that exact path.
4. Start the tool server in a second terminal: `~/.venv-builder/bin/python builder_server.py`.

**Mantle path.** Copy the `change_builder` folder next to this file into your agent's `skills/` folder
(`cp -r change_builder ~/mantle-agent/skills/`, using your agent's folder), then `rasa train` and
`rasa inspect --port 5010`. No `integrations.yml` entry is needed. The skill's tool calls the tool server for you and
sends the customer the build id, whether a file was saved, the file's path, and its sha256, straight from the server's
answer. The model does not reword them. Ask the helper for a change, for example "add a check that tells me the
line status". Keep `builder_server.py` running in the second terminal. If it is not running, the helper says it could
not reach the builder.

**Studio path.** Studio's own chat runs in containers and reads its endpoints from Studio's assistant settings, so it cannot reach this server at 127.0.0.1 in the codespace, and Rasa's docs do not say whether those settings accept MCP servers. The documented route is the downloaded project: `rasa studio download`, add the server to the downloaded `endpoints.yml` (`mcp_servers:` with `name: builder`, `url: http://127.0.0.1:8765/mcp`, `type: http`), add a flow step `call: build_change` with `mcp_server: builder` that maps a text slot to the `request` parameter, as in Rasa's MCP integration docs, then run it from files with `rasa train` and `rasa inspect`. Rasa lists MCP servers as a beta feature since Rasa 3.14. Studio's flow builder may not offer this step, so you may edit the downloaded `flows.yml` instead. Say plainly in the room that this leaves the Studio chat itself unable to call the builder, unless a test shows Studio's settings accept it.

`change_builder`'s message formatting is tested with stand-ins (`change_builder/test_change_builder.py`). Not yet run inside Mantle or on a real key by this author.

None of this has been run on a real key. The Mantle snippet follows the working pattern in
`examples/mantle-factory-agent`, which uses the same server setup and a longer `tool_timeout`. A real builder
session can take minutes, and the Mantle default is 10 seconds.

The tool server keeps a build "running" until its worker really finishes, even if the caller cancels. A second request
meanwhile is refused. Each build writes to its own folder under `scratch/` and returns its build id and the sha256 of
the file. The builder stops waiting for new events once `BUILDER_MAX_SECONDS` (300) have passed. That is not a hard limit on the whole build: the check happens when an event arrives, so the last event can take up to 120 more seconds (the request timeout), and the artifact list and download come after the check. Closing the stream does not confirm that OpenAI ended the hosted session. Mantle waits 360 seconds. Those two behaviors
are tested with stand-ins and no key in `test_builder_server.py`.
