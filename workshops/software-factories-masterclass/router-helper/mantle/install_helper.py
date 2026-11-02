"""Turn a fresh Mantle agent into the router restart helper.

  ~/.venv-mantle/bin/python PATH/TO/install_helper.py AGENT_FOLDER

AGENT_FOLDER is the folder that `rasa init --engine mantle` made. This script
  1. checks everything first (agent.yml parses, the router skill is there) and changes nothing if any check fails,
  2. moves every other skill out of skills/ into starter-skills-moved/ next to it, never deleting one, so a skill
     you wrote yourself is kept and only stops being active,
  3. copies in the router_restart skill, and
  4. sets the agent's persona and rules to the router helper's, keeping its id, language and everything else.
Only skills/, starter-skills-moved/ and agent.yml are touched. Running it twice is safe. Run `rasa train` afterwards.
Not yet run in a clean codespace.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PERSONA = (
    "You are a router support helper. You help a customer restart their router and nothing else. "
    "You are brief and plain."
)
RULES = [
    "Only help with restarting a router. For anything else, say that you can only help with restarting a router. The factory reset rule below always comes first.",
    "You can never do a factory reset and you never give instructions for one, not even steps the customer could follow themselves. If asked for a factory reset, say you cannot do that here and offer to connect the customer with a person.",
    "If the customer says only reset, reset it or reset my router, ask whether they mean a restart or a factory reset. Do not guess.",
    "Never mention banking, accounts, balances or transactions.",
]


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    agent = Path(argv[1]).resolve()
    skills, config = agent / "skills", agent / "agent.yml"
    source = HERE / "skills" / "router_restart"
    # 1. Check everything before changing anything.
    if not skills.is_dir() or not config.is_file():
        print("not a Mantle agent folder (no skills/ or agent.yml):", agent)
        return 2
    if not (source / "skill.md").is_file():
        print("the router_restart skill is missing next to this script:", source)
        return 2
    try:
        data = yaml.safe_load(config.read_text()) or {}
        if not isinstance(data, dict) or not isinstance(data.get("agent", {}), dict):
            raise ValueError("agent.yml is not a mapping with an agent: block")
        data.setdefault("agent", {})["persona"] = PERSONA
        data["rules"] = RULES
        new_config = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    except (yaml.YAMLError, ValueError, OSError) as error:
        print("nothing changed: agent.yml could not be read:", type(error).__name__)
        return 2
    others = sorted(p for p in skills.iterdir() if p.name != "router_restart")
    # 2. Change things. Other skills are moved, never deleted.
    if others:
        moved = agent / "starter-skills-moved"
        moved.mkdir(exist_ok=True)
        for path in others:
            target = moved / path.name
            n = 1
            while target.exists():
                n += 1
                target = moved / f"{path.name}-{n}"
            print("moving out of skills/:", path.name, "->", target.relative_to(agent))
            shutil.move(str(path), str(target))
    if (skills / "router_restart").exists():
        shutil.rmtree(skills / "router_restart")
    shutil.copytree(source, skills / "router_restart")
    handle, temp = tempfile.mkstemp(dir=agent, prefix=".agent.yml.")
    with os.fdopen(handle, "w") as stream:
        stream.write(new_config)
    os.replace(temp, config)
    print("installed router_restart; persona and rules set. Now run: rasa train")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
