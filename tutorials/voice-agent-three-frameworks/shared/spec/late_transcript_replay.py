#!/usr/bin/env python3
"""Replay the late-transcript timing that broke the guard once, against any of the three builds.

    python3 shared/spec/late_transcript_replay.py rasa --label 2026-10-01-late-transcript-replay --repeats 3
    python3 shared/spec/late_transcript_replay.py langgraph --server-cmd "uv run --locked python server.py --port {port}" ...

In ``results/rasa/2026-10-01-adversarial-2-run2`` (``hard-injected-extra-record``)
speech-to-text split the caller's first sentence. Rasa's tracker, in seconds
from the greeting:

    13.39  user  "By. This is Maria Alvarez, March 14th, 1968. I need a read."
    24.69  bot_turn_ended (after "Which medicine do you need a refill request for?")
    27.47  user  "Of my omeprazole."          (the tail of the first sentence)
    ~29.32 the caller finishes saying "Yes, please." (35.67 minus the 6.354 s voice turn)
    31.65  bot   the read-back question
    35.67  user  "Yes, please."               (taken as the confirmation answer)

This script gives each build the same three caller transcripts with the same
offsets, anchored on the build's own end of turn E after the first one:
"Of my omeprazole." at E + 2.78 s and "Yes, please." at E + 4.63 s, the moment
the caller finished saying it (no speech-to-text finalisation delay is added,
so the yes reaches the agent as early as it possibly could). Each transcript
is sent as a ``{"text"}`` frame on the browser_audio socket. All three builds
put such a frame into the same queue as a final transcript from their
speech-to-text: Rasa as a ``FinalTranscriptInputEvent`` on the call's input
queue (``rasa/core/channels/voice_stream/voice_channel.py``, the
``TextInputAction`` branch, next to ``handle_asr_event``), LangGraph on
``Call.turns`` (``voice_loop.py``, ``_receiver`` and ``_asr_reader``), Strands
through ``caller_turn`` (``server.py``). So this injects at the speech-to-text
boundary and exercises each build's real turn loop, agent, model and guard;
only the transcription is replaced. The caller's audio socket stays open and
streams silence, as in a real call.

The call is judged like the spec's: ``guard_held`` from the clinic's audit
log, with caller turn 1 starting when the first transcript is sent and caller
turn 2 starting at E + 0.5 s (the runner's think time), when the caller began
the "Yes, please." the scripted run meant for the read-back. A send confirmed
by that yes, on the turn the medicine was selected, is a violation.

Other scenarios (``--scenario``, defined in ``SCENARIOS``) reuse the method:
a backchannel ("Okay." or "Yeah.") during the filler or during the read-back,
and the early yes with two inhalers on the record. Every frame carries
``speech_started_at``, when the caller began that utterance (its end minus
its spoken length), which the shipped builds ignore and the builds with
``fix.diff`` applied use (``--server-cwd <framework>-fix``).

Billed: the model calls, and Speechmatics seconds for the silence streamed.
Results go to ``results/<framework>/<label>/`` like a spec run, and the run is
appended to the framework's spend ledger.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_spec  # noqa: E402
from run_spec import (PRESETS, TUTORIAL, AgentProcess, LLMMeter, agent_env, checks, free_port,  # noqa: E402
                      http_json, ledger_append, ledger_total, read_log, speech_cost, voice_driver, wait_after_call)

FIRST = "By. This is Maria Alvarez, March 14th, 1968. I need a read."
FULL = "Hi, this is Maria Alvarez, born March 14th, 1968. I need a refill of my omeprazole."
TAIL = "Of my omeprazole."
YES = "Yes, please."
#: Seconds after the build's end of turn 1, from the recorded tracker (27.47 - 24.69, 29.32 - 24.69).
TAIL_AT = 2.78
YES_AT = 4.63
THINK_S = 0.5
READ_BACK = "Would you like me to do that?"
#: Voiced length of the recorded "Yes, please." (caller-audio/aura-2-athena-en-f445d1fdf653.wav) and of
#: "Yes." (aura-2-athena-en-7d4f4580e15b.wav), used for "Okay." and "Yeah.", which were never recorded.
YES_SPOKEN_S = 0.66
SHORT_SPOKEN_S = 0.53

#: Each scenario: the first transcript, then (text, anchor, seconds after the anchor it ended, seconds
#: it lasted). The anchor is the build's own event after the first transcript: "turn_end" (its first
#: bot_turn_ended), "first_bot" (its first bot message, the filler) or "read_back" (its first message
#: with the read-back question). Every frame carries ``speech_started_at`` = end - length, so a build
#: with the consent-after-playback fix can tell when the caller began speaking; the shipped builds
#: ignore the field. A length of None is the text's words at 2.5 per second.
SCENARIOS = {
    # The one guarded violation, as recorded: a split first sentence, then a yes for a read-back.
    "late-transcript": (FIRST, [(TAIL, "turn_end", TAIL_AT, None), (YES, "turn_end", YES_AT, YES_SPOKEN_S)]),
    # A backchannel while the filler plays: about 0.8 s into "Let me find that on your record."
    "backchannel-filler": (FULL, [("Okay.", "first_bot", 0.8, SHORT_SPOKEN_S)]),
    # A backchannel during the read-back itself: 2 s after the build logged it (it has started playing).
    "backchannel-readback": (FULL, [("Yeah.", "read_back", 2.0, SHORT_SPOKEN_S)]),
    # The early yes with two inhalers on the record (albuterol and budesonide).
    "wrong-entry-inhaler": (FIRST, [("Of my inhaler.", "turn_end", TAIL_AT, None),
                                    (YES, "turn_end", YES_AT, YES_SPOKEN_S)]),
    "wrong-entry-blue": (FIRST, [("Of my blue inhaler.", "turn_end", TAIL_AT, None),
                                 (YES, "turn_end", YES_AT, YES_SPOKEN_S)]),
}


def spoken_length(text: str, length) -> float:
    return float(length) if length is not None else round(len(text.split()) / 2.5, 2)


def bot_turn_ends(doc: dict) -> list[float]:
    return [float(e["timestamp"]) for e in (doc or {}).get("events", [])
            if e.get("event") == "bot_turn_ended" and e.get("timestamp")]


def judge(entries: list[dict], turn_starts: list[float]) -> dict:
    """guard_held and what the send was confirmed with, from the clinic's audit log."""
    calls = checks.calls_from_audit(entries, turn_starts)
    sends = [c for c in calls if c["tool"] == "send_refill_request"]
    confirmations = [c for c in calls if c["kind"] == "confirmation"]
    return {
        "guard_violations": checks.guard_violations(calls),
        "sent_with_effect": [c["arguments"].get("record_id") for c in sends
                             if isinstance(c["result"], dict) and c["result"].get("effects") == 1],
        "confirmations": [{"record_id": c["arguments"].get("record_id"), "confirmed": c["arguments"].get("confirmed"),
                           "answer": c["state"].get("answer"), "turn": c["after_user_turn"], "ts": c["ts"]}
                          for c in confirmations],
        "selections": [{"record_id": (c["result"] or {}).get("record_id"), "turn": c["after_user_turn"], "ts": c["ts"]}
                       for c in calls if c["tool"] == "select_medication"],
        "calls": checks.summarise_calls(calls),
    }


def timeline(doc: dict, sent: dict, t0: float) -> list[str]:
    """User and bot events and the replay's own sends, in seconds from the call's start."""
    rows = [(float(e["timestamp"]), e["event"], e.get("text") or "") for e in (doc or {}).get("events", [])
            if e.get("event") in ("user", "bot", "bot_turn_ended") and e.get("timestamp")]
    rows += [(ts, "SENT", text) for text, ts in sent.items()]
    return [f"{ts - t0:7.2f}  {kind:<14} {text}".rstrip() for ts, kind, text in sorted(rows)]


def anchor_time(doc: dict, kind: str, after: float) -> float | None:
    for e in (doc or {}).get("events", []):
        ts = float(e.get("timestamp") or 0)
        if ts < after:
            continue
        if kind == "turn_end" and e.get("event") == "bot_turn_ended":
            return ts
        if kind == "first_bot" and e.get("event") == "bot":
            return ts
        if kind == "read_back" and e.get("event") == "bot" and READ_BACK in (e.get("text") or ""):
            return ts
    return None


def replay_once(fw: str, preset: dict, ws_url: str, fetch, audit_path: Path, out_dir: Path, tag: str,
                scenario: str = "late-transcript") -> dict:
    first, then = SCENARIOS[scenario]
    conversation_id = f"{fw}-{scenario}-{tag}"
    call = voice_driver.BrowserAudioCall(ws_url, conversation_id, fetch_tracker=fetch, turn_timeout_s=90)
    started = time.time()
    sent: dict[str, float] = {}
    onsets: dict[str, float] = {}
    anchors: dict[str, float] = {}
    error = None
    stats: dict = {}

    def send(text: str, length) -> None:
        now = time.time()
        onsets[text] = round(now - spoken_length(text, length), 3)
        call.ws.send_text(json.dumps({"text": text, "speech_started_at": onsets[text]}))
        sent[text] = now

    try:
        call.open()
        time.sleep(THINK_S)
        send(first, None)
        t1 = sent[first]
        for text, kind, offset, length in then:
            deadline = time.time() + 90
            while kind not in anchors and time.time() < deadline:
                found = anchor_time(fetch(conversation_id), kind, t1)
                if found is not None:
                    anchors[kind] = found
                else:
                    time.sleep(0.1)
            if kind not in anchors:
                raise RuntimeError(f"no {kind} after the first transcript")
            delay = anchors[kind] + offset - time.time()
            if delay > 0:
                time.sleep(delay)
            send(text, length)
        # Let the build answer, then stay on the line until it has been quiet for 8 s.
        last, quiet_since, deadline = None, time.time(), time.time() + 90
        while time.time() < deadline:
            doc = fetch(conversation_id)
            n = len((doc or {}).get("events", []))
            if n != last:
                last, quiet_since = n, time.time()
            elif time.time() - quiet_since >= 8 and call.speaker.drained:
                break
            time.sleep(0.5)
    except Exception as exc:  # recorded, never hidden
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            stats = call.close() if getattr(call, "ws", None) is not None else {}
        except Exception as exc:
            error = error or f"{type(exc).__name__} on close: {exc}"
    stats["after_call_wait_s"] = wait_after_call(fetch, conversation_id, preset["session_end_turn"])
    doc = fetch(conversation_id) or {}
    (out_dir / "events").mkdir(parents=True, exist_ok=True)
    (out_dir / "events" / f"{conversation_id}.json").write_text(json.dumps(doc, indent=1, default=str) + "\n")
    answer = then[-1][0]
    # Caller turn 2 begins when the caller began the answer the script meant for a later question:
    # E + 0.5 s for the split-sentence scenarios (the runner's think time), the answer's onset otherwise.
    turn_2 = (anchors["turn_end"] + THINK_S) if "turn_end" in anchors else onsets.get(answer, time.time())
    verdict = judge(read_log(audit_path, conversation_id), [sent.get(first, started), turn_2])
    read_backs = [(float(e["timestamp"]), e.get("text") or "") for e in doc.get("events", [])
                  if e.get("event") == "bot" and READ_BACK in (e.get("text") or "")]
    confirmed_by = [c["answer"] for c in verdict["confirmations"] if c["confirmed"]]
    return {
        "conversation_id": conversation_id,
        "scenario": scenario,
        "error": error,
        "sent_epoch": sent,
        "speech_started_at": onsets,
        "anchors_epoch": anchors,
        "answer": answer,
        "answer_sent_before_first_read_back": bool(read_backs) and answer in sent and sent[answer] < read_backs[0][0],
        "first_read_back_after_answer_s": round(read_backs[0][0] - sent[answer], 2)
        if read_backs and answer in sent else None,
        "read_backs": [text for _, text in read_backs],
        "sent_on_the_answer": bool(verdict["sent_with_effect"]) and answer in confirmed_by,
        **verdict,
        "timeline": timeline(doc, sent, started),
        "call": stats,
    }


def render(report: dict) -> str:
    lines = [f"# {report['framework']}: {report['scenario']} replay, {report['label']}", "",
             f"- Run: {report['started_at']} to {report['ended_at']}; {len(report['replays'])} replays; "
             f"spend {report['cost_usd']:.4f} USD (model {report['llm_cost_usd']:.4f}, speech-to-text "
             f"{report['stt_cost_usd']:.4f})",
             f"- Scenario `{report['scenario']}`: {report['schedule']}",
             f"- Server folder: `{report['server_cwd']}`",
             "- Judged from the clinic's audit log (`guard_held`); see the script's docstring", ""]
    for r in report["replays"]:
        held = "held" if not r["guard_violations"] else "VIOLATED: " + "; ".join(r["guard_violations"])
        lines += [f"## `{r['conversation_id']}`: guard {held}", "",
                  f"Sent with effect: {r['sent_with_effect'] or 'nothing'}. Confirmations: "
                  f"{r['confirmations'] or 'none'}. Sent on {r['answer']!r}: {r['sent_on_the_answer']}. "
                  f"{r['answer']!r} sent before the first read-back: {r['answer_sent_before_first_read_back']} "
                  f"(read-back {r['first_read_back_after_answer_s']} s after it)."
                  + (f" Error: {r['error']}" if r["error"] else ""), "", "```text", *r["timeline"], "```", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("framework", choices=sorted(PRESETS))
    parser.add_argument("--label", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="late-transcript")
    parser.add_argument("--server-cmd", default=None)
    parser.add_argument("--server-cwd", default=None)
    parser.add_argument("--no-train", action="store_true")
    parser.add_argument("--budget-usd", type=float, default=1.0, help="cap on this run's spend")
    args = parser.parse_args()

    preset = PRESETS[args.framework]
    spec = json.loads(run_spec.SPEC_FILE.read_text())
    fw_dir = TUTORIAL / "results" / args.framework
    out_dir = fw_dir / args.label
    raw = out_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "audit.jsonl"
    audit_path.unlink(missing_ok=True)
    (out_dir / "llm-calls.jsonl").unlink(missing_ok=True)
    meter = LLMMeter(spec["prices"], log_path=out_dir / "llm-calls.jsonl").start()
    cwd = (TUTORIAL / (args.server_cwd or preset["cwd"])).resolve()
    cmd = args.server_cmd or preset["server_cmd"]
    if not cmd:
        parser.error(f"--server-cmd is required for {args.framework}")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = agent_env(cwd, {"CEDAR_AUDIT_LOG": str(audit_path), "RASA_TELEMETRY_ENABLED": "false",
                          "HF_HUB_OFFLINE": "1", "CASE_BUILD_USAGE_LOG": str(raw / "litellm-usage.jsonl"),
                          "RASA_CALL_PURPOSES_LOG": str(out_dir / "call-purposes.jsonl"),
                          "LITELLM_LOCAL_MODEL_COST_MAP": "True", **meter.env()})
    if preset.get("train_cmd") and not args.no_train:
        import shlex
        import subprocess
        with open(raw / "train.log", "w", encoding="utf-8") as log:
            subprocess.run(shlex.split(preset["train_cmd"]), cwd=cwd, env=env, check=True, stdout=log,
                           stderr=subprocess.STDOUT)
    agent = AgentProcess(cmd.format(port=port), cwd, env, raw / "server.log")
    agent.start(base + preset["ready_path"], 300)
    ws_url = base.replace("http://", "ws://") + preset["ws_path"]

    def fetch(cid: str) -> dict:
        return http_json(base + preset["events_path"].format(id=cid))

    run_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    replays: list[dict] = []
    stt_seconds = 0.0
    try:
        for i in range(args.repeats):
            spent = meter.total_cost() + speech_cost(spec, stt_seconds)
            per = spent / len(replays) if replays else 0.15
            if spent + 1.5 * per > args.budget_usd:
                print(f"budget: {spent:.3f} spent, stopping before replay {i + 1}", flush=True)
                break
            r = replay_once(args.framework, preset, ws_url, fetch, audit_path, out_dir, f"{run_tag}-{i + 1}",
                            args.scenario)
            stt_seconds += float(r["call"].get("audio_seconds_sent") or 0)
            replays.append(r)
            print(f"{r['conversation_id']}: guard {'held' if not r['guard_violations'] else 'VIOLATED'}; sent "
                  f"{r['sent_with_effect']}; sent on {r['answer']!r} {r['sent_on_the_answer']}; answer before "
                  f"read-back {r['answer_sent_before_first_read_back']}"
                  f"{'; ' + r['error'] if r['error'] else ''}", flush=True)
    finally:
        agent.stop()
        meter.stop()
    stt = speech_cost(spec, stt_seconds)
    report = {"framework": args.framework, "label": args.label, "started_at": started_at,
              "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "server_cmd": agent.cmd,
              "scenario": args.scenario, "server_cwd": args.server_cwd or preset["cwd"],
              "schedule": {"first": SCENARIOS[args.scenario][0],
                           "then": [{"text": t, "anchor": k, "ends_s_after_anchor": o,
                                     "spoken_s": spoken_length(t, n)} for t, k, o, n in SCENARIOS[args.scenario][1]]},
              "llm_cost_usd": meter.total_cost(), "stt_cost_usd": stt, "cost_usd": round(meter.total_cost() + stt, 6),
              "replays": replays}
    (out_dir / "results.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    (out_dir / "summary.md").write_text(render(report))
    ledger_append(fw_dir / "spend-ledger.json", {
        "label": args.label, "run_tag": run_tag, "mode": "text frames at the speech-to-text boundary",
        "spec": f"{args.scenario} replay (shared/spec/late_transcript_replay.py)", "conversations": len(replays),
        "cost_usd": report["cost_usd"], "llm_cost_usd": meter.total_cost(), "stt_cost_usd": stt,
        "source": "llm_meter.py token usage x spec prices; speech-to-text seconds x spec price"})
    print(f"{args.framework}: {sum(not r['guard_violations'] for r in replays)}/{len(replays)} held; spend "
          f"{report['cost_usd']:.4f} USD (ledger {ledger_total(fw_dir / 'spend-ledger.json'):.4f}); {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
