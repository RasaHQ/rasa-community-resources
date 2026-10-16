"""Print service states to use when rehearsing an assistant's replies."""
import argparse
import json
from pathlib import Path
import tempfile

from appointment_exchange import LostReply, Scheduler


def run(scenario):
    with tempfile.TemporaryDirectory() as folder:
        service = Scheduler(Path(folder) / "schedule.sqlite")
        try:
            service.seed()
            service.hold("hold-1", "customer-1", "Wednesday 11:00", "fibre", 120, 100)
            before = service.active()
            try:
                reply = service.exchange(
                    "request-1", "visit-1", 1, "hold-1", "customer-1", "fibre",
                    now=120 if scenario == "expiry" else 110,
                    fail_at={"lost-reply": "after_commit",
                             "write-failure": "after_old_release"}.get(scenario))
            except LostReply:
                reply = {"status": "no_reply_received"}
            except RuntimeError:
                reply = {"status": "service_error"}
            return {"evidenceKind": "synthetic single-database service",
                    "scenario": scenario, "before": before,
                    "callerObserved": reply,
                    "lookupOriginalKey": service.lookup("request-1"),
                    "after": service.active()}
        finally:
            service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["expiry", "lost-reply", "write-failure"])
    print(json.dumps(run(parser.parse_args().scenario), indent=2, sort_keys=True))
