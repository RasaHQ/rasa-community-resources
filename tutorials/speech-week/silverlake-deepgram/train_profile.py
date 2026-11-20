"""Train this exact bank profile from a temporary source-only project."""
import argparse
import sys
import tempfile
from pathlib import Path
from run_demo import BANK, prepare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["train"])
    parser.parse_args()
    sys.path.insert(0, str(BANK))
    from rasa.mantle.model_archive.snapshot import package_model_archive
    with tempfile.TemporaryDirectory(prefix="silverlake-deepgram-training-") as raw:
        root = Path(raw)
        project = prepare(root / "project")
        result = package_model_archive(str(project / "agent.yml"), str(root / "models"),
                                       fixed_model_name="silverlake-deepgram", validate=True)
        print("Profile source packaged and validated; no model or speech call.")
        return int(result.code)


if __name__ == "__main__":
    raise SystemExit(main())
