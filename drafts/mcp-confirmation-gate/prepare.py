"""Prepare isolated source configurations; never copy credentials or environments."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def prepare(variant, destination, port, scripted_model_port=None):
    if variant not in {"gated", "ungated"} or not 1024 <= port <= 65535:
        raise ValueError("Choose a known variant and an unprivileged MCP port")
    if destination.exists():
        raise FileExistsError("Retain existing work; choose a new run directory")
    if scripted_model_port is not None and (
            not 1024 <= scripted_model_port <= 65535 or scripted_model_port == port):
        raise ValueError("Choose a separate unprivileged scripted model port")
    template = "integrations.scripted.yml.in" if scripted_model_port is not None else "integrations.yml.in"
    integrations = (ROOT / template).read_text().replace("MCP_PORT", str(port))
    if scripted_model_port is not None:
        integrations = integrations.replace("MODEL_PORT", str(scripted_model_port))
    files = {
        "agent.yml": (ROOT / "agent.yml").read_text(),
        "integrations.yml": integrations,
        "skills/review_case/skill.md": (ROOT / "skill.md.in").read_text().replace(
            "CONFIRMATION_ENABLED", "true" if variant == "gated" else "false"),
        "skills/review_case/tools.py": (ROOT / "runtime_tools.py").read_text(),
    }
    destination.mkdir(parents=True)
    for name, content in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    receipt = {"variant": variant, "mcp_port": port,
               "model_mode": "scripted-loopback" if scripted_model_port is not None else "provider",
               "scripted_model_port": scripted_model_port,
               "files": {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                         for name in files},
               "scope": "Source preparation only; no training, model call or runtime qualification"}
    (destination / "variant.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("gated", "ungated"), required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--mcp-port", type=int, default=8937)
    parser.add_argument("--scripted-model-port", type=int,
                        help="Use the local scripted Chat Completions fixture, not a model provider")
    args = parser.parse_args()
    print(json.dumps(prepare(args.variant, args.run_dir, args.mcp_port, args.scripted_model_port), indent=2))
