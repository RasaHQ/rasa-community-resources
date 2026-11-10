"""One bounded JSON request per process; SQLite retains the original graph run."""
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from statement_worker.graph import ROWS, build_graph, valid_month


def handle(request, connection):
    if set(request) - {"action", "run_id", "demo_owner", "month"}:
        return {"error": "unexpected_input"}
    run_id = request.get("run_id", "")
    owner = request.get("demo_owner")
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id) or owner not in ROWS:
        return {"error": "invalid_context"}
    graph = build_graph(SqliteSaver(connection))
    config = {"configurable": {"thread_id": run_id}}
    previous = graph.get_state(config)
    if previous.values and previous.values.get("demo_owner") != owner:
        return {"error": "context_mismatch"}
    action = request.get("action")
    if action == "start":
        if not previous.values:
            graph.invoke({"run_id": run_id, "demo_owner": owner, "status": "started"}, config)
    elif action == "resume":
        if not previous.values:
            return {"error": "run_missing"}
        if not valid_month(request.get("month")):
            return {"error": "invalid_month"}
        if previous.next:
            graph.invoke(Command(resume=request["month"]), config)
        elif previous.values.get("month") != request["month"]:
            return {"error": "completed_month_changed"}
    else:
        return {"error": "unknown_action"}
    state = graph.get_state(config)
    if state.next:
        return {"status": "needs_month", "run_id": run_id, "demo_owner": owner,
                "question": "Which month, for example 2026-10?"}
    return {"status": "complete", "run_id": run_id, "demo_owner": owner,
            "report": state.values["report"]}


def main():
    raw = sys.stdin.buffer.read(8193)
    if len(raw) > 8192:
        raise SystemExit("Input too large")
    request = json.loads(raw)
    if not isinstance(request, dict):
        raise SystemExit("Input must be an object")
    # The caller supplies a seat-owned development directory. No global database.
    directory = Path(os.environ["STATEMENT_STATE_DIR"])
    if not directory.is_dir() or any(p.is_symlink() for p in (directory, *directory.parents)):
        raise SystemExit("Use an existing real state directory")
    db = directory / "checkpoints.sqlite"
    # Reject symlinks and make a newly created database owner-readable only.
    fd = os.open(db, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    connection = sqlite3.connect(db, timeout=5, check_same_thread=False)
    try:
        print(json.dumps(handle(request, connection)))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
