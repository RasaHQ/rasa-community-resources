"""The gate for the router helper. It judges one change the builder proposed. The builder cannot edit it.

  python3 gate.py CANDIDATE.py

The candidate is a Python file that must define check_line_status(), a read-only operation. The gate:
  1. reads the file as text and refuses it if it imports the network or process modules, or names a restart
     or factory-reset command,
  2. runs the candidate in a separate process under a no-network wrapper that was proven by behavior
     (book/ready/ch06/isolation.py, checked against its pinned hash before it is run), and
  3. compares what check_line_status() returns with the expected answer.

Exit 0 ACCEPT, 1 REJECT (it prints the name of the test that failed), 2 could not judge. If no wrapper can be
proven, or isolation.py does not match its pin, the gate exits 2 and judges nothing.
"""
import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISOLATION = HERE.parent.parent / "book/ready/ch06/isolation.py"
ISOLATION_SHA256 = "3b603913b621e56215b9157eaa3ef488b63ea98e14653d8aa87529ce49adf981"
EXPECTED = {"operation": "check_line_status", "status": "ok", "changes_anything": False}
FORBIDDEN_IMPORTS = {"socket", "subprocess", "os", "shutil", "http", "urllib", "requests", "httpx", "ctypes", "asyncio"}
FORBIDDEN_WORDS = ("REBOOT", "FACTORY_RESET")


def load_isolation():
    if hashlib.sha256(ISOLATION.read_bytes()).hexdigest() != ISOLATION_SHA256:
        return None
    spec = importlib.util.spec_from_file_location("isolation", ISOLATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def static_failures(text):
    failures = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ["test_candidate_is_valid_python"]
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "open", "__import__", "compile"}:
            names.add(node.func.id)
    if names & (FORBIDDEN_IMPORTS | {"exec", "eval", "open", "__import__", "compile"}):
        failures.append("test_no_network_process_or_file_access")
    if any(word in text for word in FORBIDDEN_WORDS):
        failures.append("test_no_restart_or_reset_command")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "check_line_status" for n in tree.body):
        failures.append("test_defines_check_line_status")
    return failures


def main(argv):
    if len(argv) != 2:
        print("usage: gate.py CANDIDATE.py")
        return 2
    try:
        text = Path(argv[1]).read_text(encoding="utf-8")
    except OSError as error:
        print("could not judge:", type(error).__name__)
        return 2
    isolation = load_isolation()
    prefix = isolation.first_blocking() if isolation else None
    if prefix is None:
        print("could not judge: no proven no-network wrapper, or isolation.py does not match its pin")
        return 2
    failures = static_failures(text)
    if not failures:
        runner = "import json,runpy,sys\nns = runpy.run_path(sys.argv[1])\nprint('GATE-RESULT ' + json.dumps(ns['check_line_status']()))\n"
        done = subprocess.run([*prefix, sys.executable, "-I", "-c", runner, argv[1]], capture_output=True, text=True,
                              timeout=60, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1"})
        lines = [line for line in done.stdout.splitlines() if line.startswith("GATE-RESULT ")]
        if done.returncode != 0 or len(lines) != 1:
            failures.append("test_candidate_runs_and_returns_once")
        elif json.loads(lines[0][len("GATE-RESULT "):]) != EXPECTED:
            failures.append("test_returns_the_expected_read_only_answer")
    if failures:
        print("REJECT - failed:", ", ".join(failures))
        return 1
    print("ACCEPT - the change passed every check")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
