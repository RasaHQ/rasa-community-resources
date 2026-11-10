"""Prepare source-only variants, inspect the pinned native compiler, or read a saved replay."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS = ("bare", "referenced")
REF = "@skill.staff_handoff"


def prepare(variant, destination):
    if variant not in VARIANTS:
        raise ValueError("Unknown variant")
    if destination.exists():
        raise FileExistsError("Choose a new run directory; existing work is retained")
    destination.mkdir(parents=True)
    for name in ("agent.yml", "integrations.yml", "skills", "lib"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, destination / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copyfile(src, destination / name)
    path = destination / "skills/blocked_request/skill.md"
    if variant == "bare":
        source = path.read_text()
        if source.count(REF) != 1:
            raise ValueError("Expected exactly one reference")
        path.write_text(source.replace(REF, "staff_handoff"))
    receipt = {"variant": variant,
               "skill_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "environment": "Uses the original project's interpreter; no environment copied"}
    (destination / "variant.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def native_check(path):
    from rasa.mantle.skills.markdown_skill_compiler import compile_markdown_skill
    from rasa.mantle.skills.catalog import SkillCatalog
    from rasa.mantle.skills.validation import collect_bare_skill_mention_findings
    from rasa.mantle.orchestration.skill_executor import SkillExecutor
    from rasa.mantle.skills.skill import format_skill_target_id
    parent = compile_markdown_skill(path / "skills/blocked_request/skill.md")
    child = compile_markdown_skill(path / "skills/staff_handoff/skill.md")
    catalog = SkillCatalog(skills={parent.id: parent, child.id: child})
    # Exercise the pinned native classifier, not a model choice or full turn loop.
    executor = object.__new__(SkillExecutor)
    executor._skill_catalog = catalog
    mode, error = executor._resolve_activate_frame_type(
        format_skill_target_id(parent.id), format_skill_target_id(child.id), child, parent.id)
    if error:
        raise ValueError(error)
    return {"referenced_skills": parent.referenced_skills,
            "warnings": [{"code": f.code, "severity": f.severity}
                         for f in collect_bare_skill_mention_findings(catalog)],
            "native_activation_mode": str(mode.value),
            "scope": "Native compilation and activation classification; no model conversation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "native", "train", "run"))
    parser.add_argument("--variant", choices=VARIANTS)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=5051)
    args = parser.parse_args()
    if args.command == "prepare":
        if not args.variant:
            parser.error("prepare requires --variant")
        result = prepare(args.variant, args.run_dir)
    elif args.command == "native":
        result = native_check(args.run_dir)
    else:
        import subprocess
        if not (args.run_dir / "variant.json").is_file():
            parser.error("prepare the run directory first")
        if not 1024 <= args.port <= 65535:
            parser.error("Use an unprivileged port")
        cmd = [sys.executable, "-m", "rasa", args.command]
        if args.command == "run":
            cmd.extend(["--enable-api", "--interface", "127.0.0.1", "--port", str(args.port)])
        raise SystemExit(subprocess.run(cmd, cwd=args.run_dir.resolve()).returncode)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
