# Router restart helper

The one small agent for the dark software factory session. A customer says "restart my router".
The helper asks them to confirm, then records one command, `REBOOT`. It never records
`FACTORY_RESET`. If the customer asks for a factory reset, it says it cannot do that here and offers a person.

You can tell it works when:

1. "Restart my router" makes it ask you to confirm.
2. "Yes" makes it record `REBOOT`.
3. "Reset it" makes it ask which one you mean, and it sends nothing until you answer.
4. A factory reset request gets a refusal and an offer of a person, and nothing is recorded.

Build it on Rasa Mantle:

The self-paced tutorial builds a fresh agent with the installer below. The `mantle/`
folder also holds a completed reference project, pinned by its `pyproject.toml` and
`uv.lock`. To inspect that reference independently, run `uv sync --locked`,
`uv run rasa train`, and `uv run python -m unittest discover -s . -v` from `mantle/`,
with your own `RASA_LICENSE` and `OPENAI_API_KEY` in the environment. Training and the
archive tests are separate from a live conversation test.

- Create a Mantle agent (`rasa init --engine mantle --no-prompt` in a new folder), then turn it
  into the router helper. The script checks first and changes nothing if anything is wrong, moves the starter (banking) skills out of `skills/` into `starter-skills-moved/` without deleting them, copies in the router skill, and sets
  a router-only persona and rules, keeping everything else in `agent.yml`:

  ```
  ~/.venv-mantle/bin/python <this folder>/mantle/install_helper.py <your agent>
  cd <your agent> && ~/.venv-mantle/bin/rasa train
  ~/.venv-mantle/bin/rasa inspect --port 5010
  ```

  It was run in a fresh test codespace on Nov 2 by a tester, not by an unaided attendee. It needs PyYAML, which Rasa's environment has, and its two tests pass in an
  environment with PyYAML. The skill follows Rasa's Mantle docs for a tool with a confirmation.

First check: `python3 check_helper.py mantle/skills/router_restart/tools.py`. It passes when a restart records
`REBOOT`, fails when it records anything else, and exits 2 when it cannot find a command. Change
`REBOOT` to `FACTORY_RESET` in `tools.py` and run it again to see it fail. Its tests are in
`test_check_helper.py` and need only Python.
