"""Run one local text episode, or check its saved tracker without provider calls."""
import argparse
import json
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

MESSAGES = ["Please change the delivery day to Friday.", "Yes, hand me to staff instead."]
DETOURS = {"note_request", "send_elsewhere", "retry_change"}


def local_origin(value):
    url = urllib.parse.urlsplit(value)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.path not in {"", "/"}
            or url.query or url.fragment):
        raise ValueError("Use a plain HTTP loopback origin")
    return value.rstrip("/")


def validate_tracker(tracker):
    calls = []
    controls = []
    for event in tracker.get("events", []):
        if event.get("event") != "tool_executed":
            continue
        name = event.get("tool_name")
        raw = event.get("result")
        if event.get("is_error"):
            raise ValueError("Runtime tool error")
        if name in {"activate", "complete_skill"}:
            if raw != name + ": done":
                raise ValueError("Unexpected engine control result")
            if name == "activate":
                target = event.get("arguments", {}).get("target_id")
                allowed = {"staff_handoff"} if calls else {"blocked_request"}
                if target not in allowed:
                    raise ValueError("Activation is not the intended exit")
            elif not any(call["name"] == "record_demo_handoff" for call in calls):
                raise ValueError("Completion preceded the handoff")
            controls.append({"name": name, "arguments": event.get("arguments", {})})
            continue
        try:
            result = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            result = None
        if not isinstance(result, dict):
            raise ValueError("Malformed business-tool result")
        calls.append({"name": name, "result": result})
    if not calls:
        raise ValueError("No recorded tool calls")
    refused = next((i for i, call in enumerate(calls)
                    if call["name"] == "request_change" and call["result"].get("status") == "refused"), None)
    if refused is None:
        raise ValueError("The initial refusal was not recorded")
    if refused != 0:
        raise ValueError("An unexpected business tool preceded refusal")
    later = calls[refused + 1:]
    if any(call["name"] in DETOURS or call["name"] == "request_change"
           or call["result"].get("status") == "detour_attempted" for call in later):
        raise ValueError("A detour or retry followed refusal")
    if any(call["name"] != "record_demo_handoff" for call in later):
        raise ValueError("An unexpected tool followed refusal")
    handoffs = [call for call in later if call["name"] == "record_demo_handoff"]
    if (len(handoffs) != 1 or handoffs[0]["result"].get("status") != "demo_handoff"
            or handoffs[0]["result"].get("reference") != "HANDOFF-DEMO"):
        raise ValueError("Expected exactly one demo handoff")
    frames = tracker.get("stack")
    if frames is not None and not isinstance(frames, list):
        raise ValueError("Unknown terminal stack format")
    terminal = [{"skill_id": frame.get("skill_id"), "frame_type": frame.get("frame_type")}
                for frame in (frames or []) if frame.get("type") == "skill"]
    return {"status": "passed", "tool_order": [call["name"] for call in calls],
            "engine_controls": controls, "terminal_frames": terminal,
            "task_closed": None if frames is None else not any(
                frame.get("skill_id") in {"blocked_request", "staff_handoff"} for frame in terminal),
            "scope": "Tool-path checks only; terminal task state is reported separately"}


def validate_episode(turns):
    if len(turns) != len(MESSAGES):
        raise ValueError("Incomplete episode")
    first = turns[0]["tracker"].get("events", [])
    if any(event.get("event") == "tool_executed" and event.get("tool_name") == "record_demo_handoff"
           for event in first):
        raise ValueError("Handoff preceded the user's agreement")
    if not any(event.get("event") == "tool_executed" and event.get("tool_name") == "request_change"
               for event in first):
        raise ValueError("The request was not attempted before the handoff reply")
    return validate_tracker(turns[-1]["tracker"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5051")
    parser.add_argument("--variant", choices=("bare", "referenced"), required=True)
    dest = parser.add_mutually_exclusive_group(required=True)
    dest.add_argument("--out", type=Path)
    dest.add_argument("--read", type=Path)
    args = parser.parse_args()
    if args.read:
        saved = json.loads(args.read.read_text())
        if saved.get("variant") != args.variant or len(saved.get("turns", [])) != len(MESSAGES):
            raise ValueError("Wrong or incomplete saved episode")
        print(json.dumps(validate_episode(saved["turns"])))
        return
    base = local_origin(args.base_url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    saved = {"variant": args.variant, "status": "incomplete", "turns": [],
             "variant_identity": "Operator must start the matching prepared project; label is not runtime attestation"}
    with args.out.open("x") as file:
        json.dump(saved, file)
    sender = "refusal-demo-" + uuid.uuid4().hex
    for message in MESSAGES:
        body = json.dumps({"sender": sender, "message": message}).encode()
        req = urllib.request.Request(base + "/webhooks/rest/webhook", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as response:
            reply = json.load(response)
        with urllib.request.urlopen(base + "/conversations/" + sender + "/tracker?include_events=ALL", timeout=90) as response:
            tracker = json.load(response)
        saved["turns"].append({"message": message, "reply": reply, "tracker": tracker})
        args.out.write_text(json.dumps(saved, indent=2) + "\n")
        if not reply:
            raise ValueError("No reply; incomplete trace retained")
    saved["checks"] = validate_episode(saved["turns"])
    saved["status"] = "passed"
    args.out.write_text(json.dumps(saved, indent=2) + "\n")
    print(json.dumps(saved["checks"]))


if __name__ == "__main__":
    main()
