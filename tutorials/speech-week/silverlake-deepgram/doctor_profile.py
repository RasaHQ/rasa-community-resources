"""Check local prerequisites without model, speech or bank requests."""
import importlib.metadata
import os
from pathlib import Path
import sys
import tomllib
from run_demo import BANK, HERE, load_profile_environment


def main():
    load_profile_environment()
    ready = True
    for name in ("RASA_PRO_LICENSE", "OPENAI_API_KEY", "DEEPGRAM_API_KEY"):
        present = bool(os.environ.get(name))
        if name == "RASA_PRO_LICENSE":
            present = present or bool(os.environ.get("RASA_LICENSE"))
        print(name + ": " + ("SET" if present else "MISSING"))
        ready = ready and present
    dependencies = tomllib.loads((HERE / "pyproject.toml").read_text())["project"]["dependencies"]
    expected = next(d.split("==", 1)[1] for d in dependencies if d.startswith("rasa-pro=="))
    try:
        actual = importlib.metadata.version("rasa-pro")
    except importlib.metadata.PackageNotFoundError:
        actual = "not installed"
    print("Rasa runtime: " + actual + "; expected " + expected)
    ready = ready and actual == expected
    sys.path.insert(0, str(BANK))
    try:
        from silverlake_demo.contract import SilverLakeContract
        SilverLakeContract.from_path()
        print("Vendor definitions: found and checked")
    except Exception as error:
        print("Vendor definitions: not ready (" + type(error).__name__ + "). Run make download, then make doctor.")
        ready = False
    print("Ready to start with make run." if ready else "Not ready. Correct missing prerequisites, then repeat make doctor.")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
