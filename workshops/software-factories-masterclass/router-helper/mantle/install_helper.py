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
# Persona, rules and routing prompt are the wording rasa-bench tested in a fresh Mantle project (Nov 2): router-only
# greeting, restart confirmation, "reset it" clarified, factory reset refused with a person offered.
PERSONA = (
    "You are a concise router restart helper. Help with router restarts and clarification of reset requests. "
    "You do not offer banking services."
)
RULES = [
    "On a greeting or a new conversation, say only \"Hello. I can help restart your router.\" Do not introduce or offer a factory reset unless the customer has already asked about a reset.",
    "When a router reset request is ambiguous (reset it, reset my router), ask whether the customer means a restart or a factory reset. Do not call the restart tool before they clarify that they want a restart.",
    "For a factory-reset request, say \"I cannot do a factory reset here. I can connect you with a person.\" Do not provide factory-reset instructions, not even steps the customer could follow themselves, or substitute an offer to restart after this refusal.",
    "A restart preserves the Wi-Fi name and password. Call the restart tool only for a restart request; the engine owns its confirmation. Never report a command as sent before the tool succeeds.",
]
ROUTING_NO_ACTIVE_SKILL = (
    "Router restart and ambiguous-reset clarification are supported conversations in router_restart, and factory-reset refusal is a supported conversation in factory_reset_refusal. "
    "Activate router_restart for requests such as \"restart my router\" or \"reset it\", and factory_reset_refusal for \"factory reset\". "
    "Refusing a factory reset with a human-handoff offer is supported; do not route these router requests to the generic cannot-help fallback."
)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    agent = Path(argv[1]).resolve()
    skills, config = agent / "skills", agent / "agent.yml"
    SKILLS = ("router_restart", "factory_reset_refusal")
    # 1. Check everything before changing anything.
    if not skills.is_dir() or not config.is_file():
        print("not a Mantle agent folder (no skills/ or agent.yml):", agent)
        return 2
    if not all((HERE / "skills" / name / "skill.md").is_file() for name in SKILLS):
        print("a router skill is missing next to this script:", HERE / "skills")
        return 2
    try:
        data = yaml.safe_load(config.read_text()) or {}
        if not isinstance(data, dict) or not isinstance(data.get("agent", {}), dict):
            raise ValueError("agent.yml is not a mapping with an agent: block")
        data.setdefault("agent", {})["persona"] = PERSONA
        data["rules"] = RULES
        data.setdefault("prompts", {})["routing_no_active_skill"] = ROUTING_NO_ACTIVE_SKILL
        new_config = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    except (yaml.YAMLError, ValueError, OSError) as error:
        print("nothing changed: agent.yml could not be read:", type(error).__name__)
        return 2
    others = sorted(p for p in skills.iterdir() if p.name not in SKILLS)
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
    for name in SKILLS:
        if (skills / name).exists():
            shutil.rmtree(skills / name)
        shutil.copytree(HERE / "skills" / name, skills / name)
    handle, temp = tempfile.mkstemp(dir=agent, prefix=".agent.yml.")
    with os.fdopen(handle, "w") as stream:
        stream.write(new_config)
    os.replace(temp, config)
    print("installed router_restart; persona and rules set. Now run: rasa train")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
