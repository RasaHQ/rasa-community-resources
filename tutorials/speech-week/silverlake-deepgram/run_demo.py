"""Run committed SilverLake source with this separate locked Deepgram rc1 profile.

Only source/config files enter the temporary project. The bank host, SOAP client,
journal, adapter, hooks and policy are imported unchanged from the same checkout.
This remains a fictional local SOAP mock, never a real bank connection.
"""
from pathlib import Path
import os
import sys
import tempfile

HERE = Path(__file__).resolve().parent
BANK = HERE.parents[2] / "examples" / "jack-henry-silverlake"


def prepare(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for relative in ("hooks.py", "skills/banking/skill.md", "skills/banking/tools.py"):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((BANK / relative).read_bytes())
    for name in ("agent.yml", "integrations.yml", "pyproject.toml", "uv.lock"):
        (destination / name).write_bytes((HERE / name).read_bytes())
    return destination


def main():
    sys.path.insert(0, str(BANK))
    os.environ["PYTHONPATH"] = os.pathsep.join([str(BANK), os.environ.get("PYTHONPATH", "")])
    # rc1 accepts the operator's current licence name. This alias is in memory,
    # never written into the temporary project or a log.
    if not os.environ.get("RASA_LICENSE") and os.environ.get("RASA_PRO_LICENSE"):
        os.environ["RASA_LICENSE"] = os.environ["RASA_PRO_LICENSE"]
    from silverlake_demo.launcher import main as launch
    with tempfile.TemporaryDirectory(prefix="silverlake-deepgram-source-") as directory:
        project = prepare(directory)
        return launch(project, required_secrets=("RASA_LICENSE", "OPENAI_API_KEY", "DEEPGRAM_API_KEY"))


if __name__ == "__main__":
    raise SystemExit(main())
