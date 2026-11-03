"""Copy the change_builder skill into a Mantle agent folder and give custom tools time to wait for a build.

Usage:  python3 install_change_builder.py AGENT_FOLDER

Mantle stops a custom tool after agent.yml's `tool_timeout` seconds (default 10). The tool waits up to 360 seconds for the
builder, so this raises `tool_timeout` to at least 450. A larger value you already have is kept. Needs PyYAML, which Rasa's
environment has. Nothing is changed if agent.yml cannot be read.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MINIMUM_TIMEOUT = 450.0


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    agent = Path(argv[1]).resolve()
    config, skills = agent / "agent.yml", agent / "skills"
    if not config.is_file() or not skills.is_dir():
        print("not a Mantle agent folder (no agent.yml or skills/):", agent)
        return 2
    try:
        data = yaml.safe_load(config.read_text()) or {}
        if not isinstance(data, dict):
            raise ValueError("agent.yml is not a mapping")
        current = data.get("tool_timeout")
        if isinstance(current, bool) or not isinstance(current, (int, float, type(None))):
            raise ValueError("tool_timeout is not a number")
        data["tool_timeout"] = max(float(current or 0), MINIMUM_TIMEOUT)
        new_config = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    except (yaml.YAMLError, ValueError, OSError) as error:
        print("nothing changed: agent.yml could not be used:", type(error).__name__)
        return 2
    target = skills / "change_builder"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(HERE, target, ignore=shutil.ignore_patterns("test_*.py", "install_change_builder.py", "__pycache__"))
    handle, temp = tempfile.mkstemp(dir=agent, prefix=".agent.yml.")
    with os.fdopen(handle, "w") as stream:
        stream.write(new_config)
    os.replace(temp, config)
    print(f"installed change_builder; tool_timeout is {data['tool_timeout']:g} seconds. Now run: rasa train")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
