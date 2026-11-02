# Your builder, behind the router helper

1. Make a virtual environment and install: `python3 -m venv ~/.venv-builder && ~/.venv-builder/bin/pip install --upgrade openai mcp==1.28.1`.
2. Your OpenAI key (the `OPENAI_API_KEY` Codespaces secret) needs the permissions `api.agents.read`,
   `api.agents.write`, and `api.responses.write`. Never paste it into a file or a command.
3. Edit `INSTRUCTIONS` in `builder.py`, then run `~/.venv-builder/bin/python builder.py`. Watch the session's
   events. The file the agent saves is downloaded to `scratch/check_line_status.py`.
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

**Studio path.** Download the assistant (`rasa studio download`), add the same server to `endpoints.yml`
(`mcp_servers:` with `name: builder`, `url: http://127.0.0.1:8765`, `type: http`), and add a flow step
`call: build_change` with `mcp_server: builder`, mapping a text slot to the `request` parameter, as in Rasa's
MCP integration docs. Rasa lists MCP servers as a beta feature since Rasa 3.14. Studio's own flow builder
may not offer this step, so you may edit the downloaded `flows.yml` instead.

None of this has been run. The Mantle snippet follows the working pattern in
`examples/mantle-factory-agent`, which uses the same server setup and a longer `tool_timeout`. A real builder
session can take minutes, and the Mantle default is 10 seconds.
