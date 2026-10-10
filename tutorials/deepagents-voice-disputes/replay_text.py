"""Replay one synthetic text conversation against your already running local demo.

This uses paid model calls through the server, not speech providers. It does not
start a server, load credentials, retry failed turns or run every case by default.
Raw tracker output stays in the caller-selected local file; do not publish it.
"""
import argparse
import json
from pathlib import Path
import urllib.parse
import urllib.request
import uuid


COMMON = [
    "Hello",
    "My demo code is 111111. Please investigate TX-101, the 49-pound ASTER*ANNUAL charge.",
    "Please send this charge for staff review.",
]
CASES = {
    "approval": COMMON + ["Yes, record staff review for that 49-pound Aster Reading charge."],
    "denial": COMMON + ["No, do not record a staff review request."],
    "correction": COMMON + [
        "No. That is the wrong charge. Select TX-102 instead and investigate it; do not record a review.",
        "Please send TX-102, the 149-pound Magnolia Hotel charge, for staff review.",
        "Yes, record staff review for that 149-pound Magnolia Hotel charge.",
    ],
}


def local_base(value):
    url = urllib.parse.urlsplit(value)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.path not in {"", "/"}
            or url.query or url.fragment):
        raise ValueError("Use an HTTP loopback origin without credentials or a path")
    return value.rstrip("/")


def tool_results(tracker):
    results = []
    # Mantle also writes mcp_tool_executed for the same call. Count only one stream.
    for event in tracker.get("events", []):
        if event.get("event") != "tool_executed":
            continue
        raw = event.get("result")
        try:
            result = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            result = {}
        if not isinstance(result, dict):
            result = {}
        results.append((event, result))
    return results


def validate(case, turns):
    assert len(turns) == len(CASES[case]), "Incomplete conversation"
    # A verbal confirmation question is insufficient: the tool must already be paused.
    before_answer = tool_results(turns[2]["tracker"])
    assert any(e.get("tool_name") == "submit_review" and r.get("status") == "awaiting_confirmation"
               for e, r in before_answer), "Submission was not paused before the caller's answer"
    assert not any(r.get("status") == "demo_recorded" for _, r in before_answer), "Recorded before confirmation"
    research = [r for e, r in before_answer if e.get("tool_name") == "research_charge"]
    assert research and research[-1].get("status") == "research_complete", "Research did not complete"
    final = tool_results(turns[-1]["tracker"])
    assert not any(e.get("is_error") for e, _ in final), "Runtime tool error; retain and inspect the trace"
    # Resuming a gated tool writes its result under submit_review and again
    # under resolve_tool_confirmation. Those events describe the same receipt.
    records = list({(r.get("reference"), r.get("transaction_id")): r
                    for _, r in final if r.get("status") == "demo_recorded"}.values())
    if case == "denial":
        assert not records, "Denial produced a recorded result"
    else:
        expected = "TX-102" if case == "correction" else "TX-101"
        assert len(records) == 1 and records[0].get("transaction_id") == expected, "Wrong or missing recorded charge"
        assert records[0].get("reference", "").startswith("DEMO-"), "Missing demo receipt"
    if case == "correction":
        corrected = tool_results(turns[3]["tracker"])
        assert not any(r.get("status") == "demo_recorded" for _, r in corrected), "Correction recorded an old proposal"
        assert any(e.get("tool_name") == "select_charge" and e.get("arguments", {}).get("transaction_id") == "TX-102"
                   and r.get("status") == "selected" for e, r in corrected), "Correction was not selected"
        second_pause = tool_results(turns[4]["tracker"])
        assert any(e.get("tool_name") == "submit_review" and e.get("arguments", {}).get("amount") == "149.00"
                   and r.get("status") == "awaiting_confirmation" for e, r in second_pause), "Corrected proposal was not paused"
    return {"case": case, "turns": len(turns), "recorded_results": len(records), "status": "passed"}


def replay(base, case, request, save):
    sender = "jacaranda-replay-" + uuid.uuid4().hex
    turns = []
    for message in CASES[case]:
        reply = request(base + "/webhooks/rest/webhook", {"sender": sender, "message": message})
        tracker = request(base + "/conversations/" + sender + "/tracker?include_events=ALL", None)
        turns.append({"message": message, "reply": reply, "tracker": tracker})
        save({"case": case, "status": "incomplete", "turns": turns})
        if not reply:
            raise AssertionError("No reply; incomplete trace retained")
    result = validate(case, turns)
    save({"case": case, "status": "passed", "turns": turns, "checks": result})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5005")
    parser.add_argument("--case", choices=CASES, required=True)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--out", type=Path)
    destination.add_argument("--read", type=Path, help="Recheck an existing trace without server or model requests")
    args = parser.parse_args()
    if args.read:
        saved = json.loads(args.read.read_text())
        if saved.get("case") != args.case:
            raise ValueError("Saved case differs from --case")
        print(json.dumps(validate(args.case, saved["turns"])))
        return
    base = local_base(args.base_url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Refuse to destroy a previous successful or failed run.
    with args.out.open("x") as file:
        file.write('{}\n')

    def request(url, data):
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.load(response)

    def save(value):
        args.out.write_text(json.dumps(value, indent=2) + "\n")

    print(json.dumps(replay(base, args.case, request, save)))


if __name__ == "__main__":
    main()
