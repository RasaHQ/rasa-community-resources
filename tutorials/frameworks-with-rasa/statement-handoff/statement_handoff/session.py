"""Demo identity and checkpoint references are application-owned, never tool args."""
import re
import uuid
from statement_handoff.bridge import call_worker


class Session:
    def __init__(self):
        self.demo_owner = None
        self.run_id = None
        self.active_runs = set()

    def choose_demo(self, code):
        owner = {"111111": "demo-a", "222222": "demo-b"}.get(code)
        if not owner or (self.demo_owner and self.demo_owner != owner):
            return {"error": "demo_identity_refused"}
        self.demo_owner = owner
        return {"status": "demo_selected", "next_step": "Ask which month's travel spending to search."}

    async def start(self):
        if not self.demo_owner:
            return {"error": "demo_identity_missing"}
        self.run_id = uuid.uuid4().hex
        return await self._call("start")

    async def resume(self, month):
        if not self.run_id or not self.demo_owner:
            return {"error": "run_missing"}
        if not isinstance(month, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            return {"error": "invalid_month", "next_step": "Ask for a month in YYYY-MM format."}
        return await self._call("resume", month=month)

    async def _call(self, action, **extra):
        run_id = self.run_id
        if run_id in self.active_runs:
            return {"error": "lookup_busy", "next_step": "Wait for the current lookup; do not retry automatically."}
        request = {"action": action, "run_id": run_id, "demo_owner": self.demo_owner, **extra}
        self.active_runs.add(run_id)
        try:
            result = await call_worker(request)
        finally:
            self.active_runs.discard(run_id)
        if self.run_id != run_id:
            return {"error": "run_changed_during_lookup"}
        if not isinstance(result, dict):
            return {"error": "worker_invalid_result"}
        if "error" in result:
            return {"error": "lookup_unavailable", "next_step": "Explain the lookup did not complete; retry explicitly or stop."}
        if result.get("run_id") != run_id or result.get("demo_owner") != self.demo_owner:
            return {"error": "worker_context_mismatch"}
        if result.get("status") == "needs_month" and action == "start":
            return {"status": "needs_month", "question": "Which month, for example 2026-10?"}
        report = result.get("report")
        if action != "resume" or result.get("status") != "complete" or not isinstance(report, dict):
            return {"error": "worker_invalid_result"}
        if (set(report) != {"month", "currency", "pence", "row_ids"}
            or report.get("month") != extra["month"] or report.get("currency") != "GBP"
            or type(report.get("pence")) is not int or not 0 <= report["pence"] <= 10**12
            or not isinstance(report.get("row_ids"), list)
            or len(report["row_ids"]) > 100
            or any(not isinstance(row, str) or not re.fullmatch(r"S-\d{3}", row) for row in report["row_ids"])
            or len(set(report["row_ids"])) != len(report["row_ids"])):
            return {"error": "worker_invalid_result"}
        return {"status": "complete", "report": report,
                "next_step": "Explain the synthetic travel total and the rows included; this does not move money."}
