# Router restart helper

The one small agent for the dark software factory session. A customer says "restart my router".
The helper asks them to confirm, then records one command, `REBOOT`. It never records
`FACTORY_RESET` unless the customer asks for a factory reset in their own words and confirms it.

You can tell it works when:

1. "Restart my router" makes it ask you to confirm.
2. "Yes" makes it record `REBOOT`.
3. "Reset it" makes it ask which one you mean, and it sends nothing until you answer.
4. It never records `FACTORY_RESET` unasked.

Two paths build the same result:

- **Mantle path.** Create a Mantle agent (`rasa init --engine mantle --no-prompt` in a new folder), then turn it
  into the router helper. The script removes the starter (banking) skills, copies in the router skill, and sets
  a router-only persona and rules, keeping everything else in `agent.yml`:

  ```
  ~/.venv-mantle/bin/python <this folder>/mantle/install_helper.py <your agent>
  cd <your agent> && ~/.venv-mantle/bin/rasa train
  ~/.venv-mantle/bin/rasa inspect --port 5010
  ```

  Not yet run in a clean codespace. It needs PyYAML, which Rasa's environment has, and its two tests pass in an
  environment with PyYAML. The skill follows Rasa's Mantle docs for a tool with a confirmation.
- **Studio path.** Follow `studio/STEPS.md`.

First check: `python3 check_helper.py mantle/skills/router_restart/tools.py` for the Mantle path, or
`python3 check_helper.py data/studio_flows.yml` for a Studio export. It passes when a restart records
`REBOOT`, fails when it records anything else, and exits 2 when it cannot find a command. Change
`REBOOT` to `FACTORY_RESET` in `tools.py` and run it again to see it fail. Its tests are in
`test_check_helper.py` and need only Python.
