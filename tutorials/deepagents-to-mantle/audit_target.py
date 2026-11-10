"""Check the selected Mantle deployment's files and lock without provider calls."""
import argparse
import ast
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parent


def audit(root=ROOT):
    project = root / "mantle"
    lock = tomllib.loads((project / "uv.lock").read_text())
    packages = {p["name"].lower().replace("_", "-") for p in lock["package"]}
    if "deepagents" in packages:
        raise ValueError("Mantle lock still installs Deep Agents")
    if "rasa-pro" not in packages or "chinook-chat-tools" not in packages:
        raise ValueError("Mantle lock must retain Rasa and the shared business library")
    sources = [project / "skills/query_store/tools.py", root / "shared/database.py"]
    for path in sources:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            if any(name == "deepagents" or name.startswith("deepagents.") for name in names):
                raise ValueError("Target source still imports Deep Agents")
    for name in ("agent.yml", "integrations.yml", "skills/query_store/skill.md"):
        if not (project / name).is_file():
            raise ValueError("Missing Mantle configuration: " + name)
    return {"deepagents_in_target_lock": False, "target_source_imports_deepagents": False,
            "shared_library_retained": True, "provider_requests": 0,
            "scope": "Selected files and dependency lock; run native cold-load tests next"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.root), sort_keys=True))
    except (ValueError, OSError, SyntaxError) as error:
        raise SystemExit("Target audit refused: " + str(error))
