#!/usr/bin/env python3
"""A software factory whose product is a Rasa Mantle agent project.

    python factory.py tasks/a1-block-card.json candidates/block-card-good runs/block-card-good

Same loop as the first course: task -> isolated change -> independent verification -> decision. The product is a
Mantle project (agent.yml, integrations.yml, skills/), and the protected acceptance runs against the real Mantle
engine, offline: no model call, no Rasa license, no network, and none of your environment variables.

Exit status 0 ACCEPT, 1 REJECT, 2 the factory itself could not run, 3 NOT_READY (this machine cannot judge anything).
"""
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files_in(directory):
    return sorted(p for p in Path(directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def digest_tree(directory):
    """One digest for a set of files: their relative paths and contents, in a fixed order."""
    digest = hashlib.sha256()
    for path in files_in(directory):
        digest.update(path.relative_to(directory).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def prepare(spec_path):
    """Can this machine judge a Mantle project at all? Problems here are never a verdict on a change."""
    spec = json.loads(Path(spec_path).read_text())
    problems = []
    here = tuple(int(x) for x in platform.python_version_tuple()[:2])
    if here < tuple(spec["python_min"]) or here >= tuple(spec["python_below"]):
        problems.append("python %s is outside the supported window %s up to %s" % (
            platform.python_version(), ".".join(map(str, spec["python_min"])), ".".join(map(str, spec["python_below"]))))
    if "distributions" in spec:
        installed = {}
        for name, expected in spec["distributions"].items():
            try:
                version = importlib.metadata.version(name)
                installed[name] = version
                numbers = tuple(int(x) for x in version.split("."))
                if not (tuple(expected["minimum"]) <= numbers < tuple(expected["below"])):
                    problems.append(name + " is outside this verifier profile")
            except (importlib.metadata.PackageNotFoundError, ValueError):
                problems.append(name + " is not an installed supported stable release")
        try:
            if importlib.util.find_spec(spec["requires_import"]) is None:
                problems.append("the verifier capability is not installed")
        except (ImportError, ModuleNotFoundError):
            problems.append("the verifier capability is not installed")
        return installed, problems
    try:
        installed = importlib.metadata.version("rasa-pro")
    except importlib.metadata.PackageNotFoundError:
        installed = None
        problems.append("rasa-pro is not installed in this Python")
    if installed and installed != spec["rasa_pro"]:
        problems.append("rasa-pro %s is installed, this factory is pinned to %s" % (installed, spec["rasa_pro"]))
    if installed and importlib.util.find_spec(spec["requires_import"]) is None:
        problems.append("rasa-pro %s has no %s, so there is no Mantle engine to ask" % (installed, spec["requires_import"]))
    return installed, problems


def run_tests(test_path, project, scratch, discover=False, strict=False):
    """Run unittest in its own process, with a cleaned environment: no keys, no license, a throwaway HOME."""
    home = Path(scratch) / "home"
    home.mkdir(exist_ok=True)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "MANTLE_PROJECT": str(project), "PRODUCT_PROJECT": str(project), "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHON_DOTENV_DISABLED": "1", "TMPDIR": str(scratch)}
    args = [sys.executable, "-I" if strict else "-s", "-m", "unittest", "discover", "-s", str(test_path)] if discover else [sys.executable, "-I" if strict else "-s", str(test_path)]
    result = subprocess.run(args, cwd=Path(test_path if discover else Path(test_path).parent), env=env, capture_output=True, text=True, timeout=180)
    lines = result.stderr.strip().splitlines() or [""]
    ran = any(re.fullmatch(r"Ran [1-9][0-9]* tests? in .+", line) for line in lines)
    passed = result.returncode == 0 and (not strict or (ran and lines[-1] == "OK"))
    failures = [line.split(" (")[0] for line in lines if line.startswith(("FAIL:", "ERROR:"))]
    summary = "; ".join(failures) or lines[-1]
    return {"passed": passed, "summary": summary, "output": result.stderr[-2000:]}


def main(task_path, candidate_dir, run_dir, environment_path=None, pack_root=None, strict=False):
    root = Path(pack_root).resolve() if pack_root is not None else ROOT
    task = json.loads(Path(task_path).read_text())
    candidate_dir, run_dir = Path(candidate_dir), Path(run_dir)
    if run_dir.exists():
        print("refusing to reuse a run directory; keep failed runs and choose a new one", file=sys.stderr)
        return 2
    installed, problems = prepare(environment_path or ROOT / "environment.json")
    if problems:
        print("NOT_READY - " + "; ".join(problems))
        return 3
    acceptance = root / task["acceptance"]["path"]
    support = [root / item["path"] for item in task["support"]]
    record = {
        "task": task["id"],
        "candidate": candidate_dir.name,
        "candidate_digest": digest_tree(candidate_dir),
        "baseline_digest": digest_tree(root / "product"),
        "acceptance_sha256": sha256_file(acceptance),
        "support_sha256": {p.name: sha256_file(p) for p in support},
        "python": platform.python_version(),
        "rasa_pro": installed if isinstance(installed, str) else None,
        "distributions": installed if isinstance(installed, dict) else {"rasa-pro": installed},
        "environment_sha256": sha256_file(environment_path or ROOT / "environment.json"),
        "checks": [],
    }
    reasons = []

    # 1. The grader must be the one the task pinned: the suite and the helper it imports.
    if record["acceptance_sha256"] != task["acceptance"]["sha256"]:
        reasons.append("the acceptance file does not match the hash pinned in the task")
    for item in task["support"]:
        if record["support_sha256"][Path(item["path"]).name] != item["sha256"]:
            reasons.append("%s does not match the hash pinned in the task" % item["path"])

    if strict and reasons:
        record["decision"], record["reasons"] = "ERROR", reasons
        run_dir.mkdir(parents=True)
        (run_dir / "decision.json").write_text(json.dumps(record, indent=2) + "\n")
        return 2  # A corrupted verifier is not a verdict against a candidate.

    # 2. Scope: a candidate may only supply files under the task's allowed paths.
    supplied = [path.relative_to(candidate_dir).as_posix() for path in files_in(candidate_dir)]
    outside = [name for name in supplied if not any(name == prefix or (prefix.endswith("/") and name.startswith(prefix)) for prefix in task["allowed_paths"])]
    record["files_supplied"] = supplied
    links = [str(path.relative_to(candidate_dir)) for path in candidate_dir.rglob("*") if path.is_symlink()]
    if links:
        reasons.append("candidate symbolic links: " + ", ".join(links))
    if outside:
        reasons.append("files outside the allowed paths: " + ", ".join(outside))

    if not reasons:
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mantle-factory-", dir=run_dir.parent) as scratch:
            # 3. Isolated change: a fresh copy of the baseline project, the candidate's files laid over it.
            workspace = Path(scratch) / "workspace"
            shutil.copytree(root / "product", workspace / "product")
            (workspace / "product" / "skills").mkdir(exist_ok=True)
            for name in supplied:
                target = workspace / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(candidate_dir / name, target)
            project = workspace / "product"
            # The builder's own tests are recorded, never trusted.
            tests = project / "tests"
            if tests.is_dir() and not strict:
                own = run_tests(tests, project, scratch, discover=True)
            else:
                own = {"passed": None, "summary": "builder tests not run outside protected sandbox" if strict else "the candidate supplied no tests", "output": ""}
            record["checks"].append({"name": "builder's own tests (informational)", **own})
            # 4. Independent verification: the protected suite and its helper, copied from the factory.
            protected = Path(scratch) / "protected"
            protected.mkdir()
            # Some protected suites read public task parameters beside themselves.
            # Use the exact host snapshot, never a candidate-supplied tasks directory.
            if strict:
                (Path(scratch) / "tasks").mkdir()
                shutil.copyfile(task_path, Path(scratch) / "tasks" / Path(task_path).name)
            for path in [acceptance, *support]:
                shutil.copyfile(path, protected / path.name)
            verdict = run_tests(protected / acceptance.name, project, scratch, strict=strict)
            record["checks"].append({"name": "protected acceptance", **verdict})
            if not verdict["passed"]:
                reasons.append("the protected acceptance suite failed: " + verdict["summary"])

    record["decision"] = "REJECT" if reasons else "ACCEPT"
    record["reasons"] = reasons
    run_dir.mkdir(parents=True)
    (run_dir / "decision.json").write_text(json.dumps(record, indent=2) + "\n")
    print(record["decision"], "-", "; ".join(reasons) if reasons else "protected acceptance passed")
    return 1 if reasons else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    environment = None
    if "--environment" in args:
        i = args.index("--environment")
        environment = args[i + 1]
        del args[i:i + 2]
    if len(args) != 3:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(*args, environment_path=environment))
