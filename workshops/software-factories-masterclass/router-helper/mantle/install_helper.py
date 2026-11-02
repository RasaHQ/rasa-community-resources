"""Turn a fresh Mantle agent into the router restart helper.

  ~/.venv-mantle/bin/python PATH/TO/install_helper.py AGENT_FOLDER

AGENT_FOLDER is the folder that `rasa init --engine mantle` made. This script
  1. removes every starter skill (the banking examples), keeping nothing but the router skill,
  2. copies in the router_restart skill, and
  3. sets the agent's persona and rules to the router helper's, keeping its id, language and everything else.
Only the skills/ folder and agent.yml are touched. It prints what it removed. Run `rasa train` afterwards.
Not yet run in a clean codespace.
"""
import shutil
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PERSONA = (
    "You are a router support helper. You help a customer restart their router and nothing else. "
    "You are brief and plain."
)
RULES = [
    "Only help with restarting a router. For anything else, say that you can only help with restarting a router.",
    "You can never do a factory reset. If asked for one, say you cannot do that here and offer to connect the customer with a person.",
    "If the customer says only reset, ask whether they mean a restart or a factory reset.",
    "Never mention banking, accounts, balances or transactions.",
]


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    agent = Path(argv[1]).resolve()
    skills, config = agent / "skills", agent / "agent.yml"
    if not skills.is_dir() or not config.is_file():
        print("not a Mantle agent folder (no skills/ or agent.yml):", agent)
        return 2
    for folder in sorted(p for p in skills.iterdir() if p.is_dir()):
        print("removing starter skill:", folder.name)
        shutil.rmtree(folder)
    shutil.copytree(HERE / "skills" / "router_restart", skills / "router_restart")
    data = yaml.safe_load(config.read_text()) or {}
    data.setdefault("agent", {})["persona"] = PERSONA
    data["rules"] = RULES
    config.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    print("installed router_restart; persona and rules set. Now run: rasa train")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
