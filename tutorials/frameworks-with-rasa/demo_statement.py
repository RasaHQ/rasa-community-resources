"""Replay the application handoff with a real worker, without a model or Rasa server."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "statement-handoff"))
from statement_handoff.session import Session


async def replay(code, month):
    case = Session()
    selected = case.choose_demo(code)
    if "error" in selected:
        raise SystemExit("Invalid public demo code")
    pause = await case.start()
    print(json.dumps(pause, sort_keys=True))
    if pause.get("status") != "needs_month":
        raise SystemExit("Worker did not pause")
    result = await case.resume(month)
    print(json.dumps(result, sort_keys=True))
    if result.get("status") != "complete":
        raise SystemExit("Worker did not complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", choices=["111111", "222222"], default="111111")
    parser.add_argument("--month", default="2026-10")
    parser.add_argument("--worker-python", required=True)
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    # Keep the virtualenv interpreter symlink: resolving it selects base Python.
    os.environ["STATEMENT_WORKER_PYTHON"] = str(Path(args.worker_python).absolute())
    os.environ["STATEMENT_STATE_DIR"] = str(Path(args.state_dir).resolve())
    asyncio.run(replay(args.code, args.month))
