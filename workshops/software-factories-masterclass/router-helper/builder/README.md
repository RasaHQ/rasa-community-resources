# Your builder, behind the router helper

1. Make a virtual environment and install: `python3 -m venv ~/.venv-builder && ~/.venv-builder/bin/pip install --upgrade openai mcp==1.28.1`.
2. Your OpenAI key (the `OPENAI_API_KEY` Codespaces secret) needs the permissions `api.agents.read`,
   `api.agents.write`, and `api.responses.write`. Never paste it into a file or a command.
3. Edit `INSTRUCTIONS` in `builder.py`, then run `~/.venv-builder/bin/python builder.py`. Watch the session's
   events. Each build writes to its own folder, `scratch/build-<id>/check_line_status.py`, and prints the file's path and sha256. Use that exact path.
4. Start the tool server in a second terminal: `~/.venv-builder/bin/python builder_server.py`.

**Mantle path.** In your agent's `integrations.yml` add:

```yaml
mcp_servers:
  - name: builder
    url: http://127.0.0.1:8765/mcp
    tool_timeout: 360
```

In the helper's `skill.md`, import the tool (`import_tools:` with `- mcp/builder:build_change`) and tell the
skill to call `@tool.build_change` when the customer asks for a change to the helper. Then `rasa train` and
`rasa inspect --port 5010`.

**Studio path.** Studio's own chat runs in containers and reads its endpoints from Studio's assistant settings, so it cannot reach this server at 127.0.0.1 in the codespace, and Rasa's docs do not say whether those settings accept MCP servers. The documented route is the downloaded project: `rasa studio download`, add the server to the downloaded `endpoints.yml` (`mcp_servers:` with `name: builder`, `url: http://127.0.0.1:8765/mcp`, `type: http`), add a flow step `call: build_change` with `mcp_server: builder` that maps a text slot to the `request` parameter, as in Rasa's MCP integration docs, then run it from files with `rasa train` and `rasa inspect`. Rasa lists MCP servers as a beta feature since Rasa 3.14. Studio's flow builder may not offer this step, so you may edit the downloaded `flows.yml` instead. Say plainly in the room that this leaves the Studio chat itself unable to call the builder, unless a test shows Studio's settings accept it.

None of this has been run on a real key. The Mantle snippet follows the working pattern in
`examples/mantle-factory-agent`, which uses the same server setup and a longer `tool_timeout`. A real builder
session can take minutes, and the Mantle default is 10 seconds.

The tool server keeps a build "running" until its worker really finishes, even if the caller cancels. A second request
meanwhile is refused. Each build writes to its own folder under `scratch/` and returns its build id and the sha256 of
the file. The builder stops waiting for new events once `BUILDER_MAX_SECONDS` (300) have passed. That is not a hard limit on the whole build: the check happens when an event arrives, so the last event can take up to 120 more seconds (the request timeout), and the artifact list and download come after the check. Closing the stream does not confirm that OpenAI ended the hosted session. Mantle waits 360 seconds. Those two behaviors
are tested with stand-ins and no key in `test_builder_server.py`.
