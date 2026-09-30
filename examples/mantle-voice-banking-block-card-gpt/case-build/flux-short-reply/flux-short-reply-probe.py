# 2026-09-30 | from examples/mantle-voice-banking-block-card-gpt: .venv/bin/python flux-short-reply-probe.py probe --env <site checkout>/.env --out flux-short-reply-frames.jsonl ; .venv/bin/python flux-short-reply-probe.py sweep --repeats 2 --env <site checkout>/.env --out flux-short-reply-frames.jsonl ; .venv/bin/python flux-short-reply-probe.py replay --frames flux-short-reply-frames.jsonl --out flux-short-reply-replay.txt   (rasa-pro 3.21.0.dev5, wheel sha256 e7f3adb7cdb35e504856ca3a5e9c574412e9a8359bd20ac0cb15503f9a86e02b, matches PyPI and RASA_RELEASE.json; engine.py sha256 fe65f02f6d4f6965b10ef76afd33c50a5f542dfb28c0b35ebe3412936df4a8a8 in the build's .venv; companion RasaHQ/rasa-community-resources, example files identical at 3a4b810 and c2bd89f)
"""Stream the block-card build's caller WAVs straight to Deepgram Flux the way
Rasa 3.21.0.dev5 does, save every server message, then replay those messages
through Rasa's own Deepgram handler.

Run it from examples/mantle-voice-banking-block-card-gpt with that project's
.venv (rasa-pro 3.21.0.dev5). Two modes:

  probe   live, paid. Builds the ASR engine with Rasa's own factory
          (voice_channel.asr_engine_from_config) from the browser_audio `asr`
          block of integrations.yml at the channel's sample rate, connects with
          the engine's own open_websocket_connection (so the URL, query string
          and Authorization header are Rasa's), and sends audio with the
          engine's own send_audio_chunks, one 20 ms frame (640 bytes of 16 kHz
          16-bit PCM) per chunk, paced in real time as the case-build harness's
          _mic_pump does: leading silence, the WAV, trailing silence longer
          than eot_timeout_ms, then CloseStream (the engine's
          signal_audio_done). Every server message is saved with its arrival
          time; messages that arrive after CloseStream are flagged and left out
          of the classification, because inside a live call Rasa keeps
          streaming and never sends CloseStream after a turn.
  replay  offline, no key, no network. Feeds each attempt's saved messages, in
          order and up to CloseStream, to a fresh engine's
          engine_event_to_asr_event (which delegates to _DeepgramV2.parse_event,
          the method handler_probe.py drives) and records what it returns.

The key is read only inside this process from the .env file named by --env
(python-dotenv, DEEPGRAM_API_KEY only) and is never printed or saved. Request
ids are stripped from saved messages.

Differences from a live call, stated so nobody reads more into the result:
each attempt opens a fresh Flux connection with 2 s of leading silence, where
the harness keeps one connection per call and streams silence while the bot
talks; no Rasa server, tracker or TTS is involved.
"""
from __future__ import annotations

import argparse
import array
import asyncio
import datetime as dt
import hashlib
import importlib.metadata as md
import json
import math
import os
import sys
import time
import wave
from pathlib import Path

import yaml

FRAME_MS = 20
LEAD_S = 2.0
TRAIL_S = 7.0          # eot_timeout_ms is 5000; 2 s of margin
DRAIN_S = 3.0          # wait for messages after CloseStream
GAP_S = 1.0            # pause between attempts
USD_PER_MIN_LEDGER = 0.0065   # case-build/conversations.json speech_pricing.stt (promotional)
USD_PER_MIN_CAP = 0.0077      # regular Flux price from the same source; used for the cap
WHEEL_SHA256 = "e7f3adb7cdb35e504856ca3a5e9c574412e9a8359bd20ac0cb15503f9a86e02b"

BARE = "nova-970bd2042e23.wav"     # "Yes."
CONTROL = "nova-3a547787b0b7.wav"  # "Yes, that's the one."


def voiced_bounds(pcm: bytes, rate: int, dbfs: float = -40.0) -> tuple[int, int]:
    """Copy of scripts/case_builds/voice_driver.py voiced_bounds (the harness's speech_s)."""
    samples = array.array("h")
    samples.frombytes(pcm)
    hop = max(1, rate // 100)
    voiced = []
    for start in range(0, len(samples) - hop + 1, hop):
        window = samples[start:start + hop]
        rms = math.sqrt(sum(s * s for s in window) / hop) / 32768.0
        if 20 * math.log10(max(rms, 1e-9)) > dbfs:
            voiced.append(start)
    if not voiced:
        return 0, 0
    return voiced[0], voiced[-1] + hop


def strip_ids(obj):
    if isinstance(obj, dict):
        return {k: strip_ids(v) for k, v in obj.items() if "request_id" not in k.lower()}
    if isinstance(obj, list):
        return [strip_ids(v) for v in obj]
    return obj


def channel_config(project: Path) -> dict:
    return yaml.safe_load((project / "integrations.yml").read_text())["channels"]["browser_audio"]


def build_engine(project: Path):
    from rasa.core.channels.voice_stream.browser_audio import _SAMPLE_RATE_TO_FORMAT
    from rasa.core.channels.voice_stream.voice_channel import asr_engine_from_config
    ch = channel_config(project)
    fmt = _SAMPLE_RATE_TO_FORMAT[ch["sample_rate"]]
    return asr_engine_from_config(ch["asr"], fmt, "en"), fmt


def header(cmd: str, note: str = "") -> str:
    return (f"{dt.date.today().isoformat()} | {cmd}   (rasa-pro {md.version('rasa-pro')}, "
            f"wheel sha256 {WHEEL_SHA256}; companion RasaHQ/rasa-community-resources "
            f"examples/mantle-voice-banking-block-card-gpt{'; ' + note if note else ''})")


# ----------------------------------------------------------------------------- probe

async def one_attempt(project: Path, pcm: bytes, lead_s: float = LEAD_S) -> dict:
    from rasa.core.channels.voice_stream.audio_bytes import RasaAudioBytes
    engine, fmt = build_engine(project)
    n = 16000 * FRAME_MS // 1000 * 2
    silence = b"\x00" * n
    frames = [silence] * round(lead_s * 1000 / FRAME_MS)
    for i in range(0, len(pcm), n):
        f = pcm[i:i + n]
        frames.append(f + silence[: n - len(f)])
    frames += [silence] * int(TRAIL_S * 1000 / FRAME_MS)

    t_req = time.monotonic()
    await engine.connect()
    sock = engine.asr_socket
    t0 = time.monotonic()
    msgs: list[dict] = []
    close_at: list[float] = []

    async def receiver():
        try:
            async for m in sock:
                t = time.monotonic() - t0
                try:
                    body = json.loads(m)
                except Exception:
                    body = {"probe_non_json": repr(m)[:200]}
                msgs.append({"t_ms": round(t * 1000, 1),
                             "after_close_stream": bool(close_at),
                             "message": strip_ids(body)})
        except Exception as e:  # recorded, not hidden
            msgs.append({"t_ms": round((time.monotonic() - t0) * 1000, 1),
                         "after_close_stream": bool(close_at),
                         "message": {"probe_receiver_error": type(e).__name__}})

    rt = asyncio.create_task(receiver())
    deadline = time.monotonic()
    sent = 0
    for f in frames:
        await engine.send_audio_chunks(RasaAudioBytes(f, fmt))
        sent += 1
        deadline += FRAME_MS / 1000
        await asyncio.sleep(max(0.0, deadline - time.monotonic()))
    close_at.append(time.monotonic() - t0)
    try:
        await engine.signal_audio_done()
    except Exception:
        pass
    try:
        await asyncio.wait_for(rt, DRAIN_S)
    except (asyncio.TimeoutError, TimeoutError):
        rt.cancel()
    t_end = time.monotonic()
    await engine.close_connection()
    return {"frames_sent": sent, "audio_s": round(sent * FRAME_MS / 1000, 2),
            "connect_ms": round((t0 - t_req) * 1000, 1),
            "close_stream_t_ms": round(close_at[0] * 1000, 1),
            "wall_s": round(t_end - t_req, 2), "messages": msgs}


async def probe(args) -> None:
    """Mode `probe` writes a new frames file: 20 bare, 10 control, interleaved,
    each with LEAD_S of leading silence. Mode `sweep` appends to that file: the
    bare WAV with the leading silence stepped by one frame (20 ms) across one
    240 ms Flux audio window (the audio_window_end values in the probe run step
    by 0.24 s), so the utterance lands at a different offset inside the window.
    In a live call that offset is whatever the preceding silence happened to be."""
    from dotenv import dotenv_values
    key = dotenv_values(args.env).get("DEEPGRAM_API_KEY")
    if not key:
        sys.exit("DEEPGRAM_API_KEY is not set in the env file")
    os.environ["DEEPGRAM_API_KEY"] = key
    del key

    project = Path.cwd()
    audio = project / "case-build" / "caller-audio"
    manifest = json.loads((audio / "manifest.json").read_text())["files"]
    wavs = {}
    for name in (BARE, CONTROL):
        raw = (audio / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest[name]["sha256"], name
        with wave.open(str(audio / name), "rb") as w:
            assert (w.getframerate(), w.getsampwidth(), w.getnchannels()) == (16000, 2, 1)
            pcm = w.readframes(w.getnframes())
        on, off = voiced_bounds(pcm, 16000)
        wavs[name] = {"pcm": pcm, "text": manifest[name]["text"], "sha256": manifest[name]["sha256"],
                      "duration_s": round(len(pcm) / 32000, 3), "speech_on_s": on / 16000,
                      "speech_off_s": off / 16000, "speech_s": round((off - on) / 16000, 2)}

    out = Path(args.out)
    if args.mode == "probe":
        set_name = "main"
        plan = [(n, LEAD_S) for n in [BARE, BARE, CONTROL] * 10]     # 20 bare, 10 control, interleaved
        first, prior_audio, prior_wall = 1, 0.0, 0.0
    else:
        set_name = "phase-sweep"
        plan = [(BARE, round(LEAD_S + k * FRAME_MS / 1000, 2)) for _ in range(args.repeats) for k in range(12)]
        old = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        first = 1 + max(l["attempt"] for l in old if l.get("kind") == "attempt")
        prior_audio = sum(l["audio_s"] for l in old if l.get("kind") == "spend")
        prior_wall = sum(l["wall_s"] for l in old if l.get("kind") == "spend")
    engine, _ = build_engine(project)
    url = engine._get_api_url() + engine._get_query_params()   # no key in the URL
    del engine
    spent_audio = spent_wall = 0.0
    with out.open("w" if args.mode == "probe" else "a") as fh:
        if args.mode == "probe":
            fh.write(json.dumps({"receipt_header": header(" ".join(["flux-short-reply-probe.py"] + sys.argv[1:2] + ["--env <site .env>", "--out", out.name]))}) + "\n")
            fh.write(json.dumps({"kind": "config", "url": url, "channel": "browser_audio",
                                 "frame_ms": FRAME_MS, "lead_silence_s": LEAD_S, "trail_silence_s": TRAIL_S,
                                 "drain_after_close_stream_s": DRAIN_S,
                                 "usd_per_min_ledger": USD_PER_MIN_LEDGER, "usd_per_min_cap": USD_PER_MIN_CAP,
                                 "cap_usd": args.cap,
                                 "wavs": {k: {kk: vv for kk, vv in v.items() if kk != "pcm"} for k, v in wavs.items()}}) + "\n")
        else:
            fh.write(json.dumps({"kind": "sweep_config", "command": " ".join(["flux-short-reply-probe.py", "sweep", "--env <site .env>", "--out", out.name, "--repeats", str(args.repeats)]),
                                 "date": dt.date.today().isoformat(), "url": url,
                                 "lead_silence_s": sorted({l for _, l in plan}), "repeats": args.repeats,
                                 "cap_usd_including_earlier_sets": args.cap}) + "\n")
        for i, (name, lead) in enumerate(plan, first):
            w = wavs[name]
            est_next = (lead + w["duration_s"] + TRAIL_S + DRAIN_S + 2) / 60 * USD_PER_MIN_CAP
            spent_hi = max(prior_audio + spent_audio, prior_wall + spent_wall) / 60 * USD_PER_MIN_CAP
            if spent_hi + est_next > args.cap:
                fh.write(json.dumps({"kind": "stopped", "before_attempt": i, "reason": "cap"}) + "\n")
                print(f"stopping before attempt {i}: cap")
                break
            started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            r = await one_attempt(project, w["pcm"], lead)
            spent_audio += r["audio_s"]
            spent_wall += r["wall_s"]
            msgs = r.pop("messages")
            fh.write(json.dumps({"kind": "attempt", "attempt": i, "set": set_name, "lead_silence_s": lead,
                                 "wav": name, "text": w["text"], "started_utc": started,
                                 "speech_on_t_ms": round((lead + w["speech_on_s"]) * 1000, 1),
                                 "speech_off_t_ms": round((lead + w["speech_off_s"]) * 1000, 1),
                                 **r, "n_messages": len(msgs)}) + "\n")
            for m in msgs:
                fh.write(json.dumps({"kind": "message", "attempt": i, **m}) + "\n")
            fh.flush()
            evs = [m["message"].get("event") or m["message"].get("type") for m in msgs
                   if not m["after_close_stream"] and (m["message"].get("event") != "Update" or m["message"].get("transcript"))]
            print(f"{i:2d} {w['text']!r:24s} lead {lead:.2f}s audio {r['audio_s']:5.2f}s  {evs}")
            await asyncio.sleep(GAP_S)
        fh.write(json.dumps({"kind": "spend", "set": set_name, "audio_s": round(spent_audio, 2), "wall_s": round(spent_wall, 2),
                             "usd_ledger_rate": round(spent_audio / 60 * USD_PER_MIN_LEDGER, 6),
                             "usd_regular_rate": round(spent_audio / 60 * USD_PER_MIN_CAP, 6),
                             "usd_regular_rate_on_wall_time": round(spent_wall / 60 * USD_PER_MIN_CAP, 6)}) + "\n")
    print(f"audio {spent_audio:.2f}s wall {spent_wall:.2f}s "
          f"~${spent_audio / 60 * USD_PER_MIN_LEDGER:.4f} (ledger) ~${spent_audio / 60 * USD_PER_MIN_CAP:.4f} (regular)")


# ----------------------------------------------------------------------------- replay

def classify(msgs: list[dict]) -> tuple[str, str]:
    """Class of the TurnInfo sequence before CloseStream. Flux also sends Update
    frames with an empty transcript every 240 ms, before and after a turn; they
    are not counted as "an Update" here, because _DeepgramV2.parse_event returns
    None for them (L282-283) and does not touch the buffer."""
    turn = [m["message"] for m in msgs if not m["after_close_stream"] and m["message"].get("type") == "TurnInfo"]
    marks = [m for m in turn if m.get("event") != "Update"]
    evs = [m.get("event") for m in marks]
    where = " ".join(f"{m.get('event')}[{m.get('turn_index')}]={m.get('transcript')!r}"
                     for i, m in enumerate(turn) if m.get("transcript")
                     and (m.get("event") != "Update" or i == 0 or turn[i - 1].get("transcript") != m.get("transcript")
                          or turn[i - 1].get("event") != "Update")) or "-"
    if not marks and not any(m.get("transcript") for m in turn):
        return "D nothing", where
    if evs.count("StartOfTurn") > 1 or evs.count("EndOfTurn") > 1 or not evs:
        return "X other: " + ",".join(evs or ["Update only"]), where
    if "EndOfTurn" not in evs:
        return "X other (no EndOfTurn before CloseStream): " + ",".join(evs), where
    eot_i = next(i for i, m in enumerate(turn) if m.get("event") == "EndOfTurn")
    ti = turn[eot_i].get("turn_index")
    if "StartOfTurn" not in evs:
        upd = [m for m in turn[:eot_i] if m.get("event") == "Update" and m.get("transcript") and m.get("turn_index") == ti]
        return ("C EndOfTurn only" if not upd else "X other: Update(s),EndOfTurn"), where
    sot_i = next(i for i, m in enumerate(turn) if m.get("event") == "StartOfTurn")
    if sot_i > eot_i:
        return "X other: " + ",".join(evs), where
    upd = [m for m in turn[sot_i + 1:eot_i] if m.get("event") == "Update" and m.get("transcript")]
    return ("A SoT, Update(s), EoT" if upd else "B SoT, EoT, no Update"), where


def replay(args) -> None:
    os.environ.setdefault("DEEPGRAM_API_KEY", "offline-replay-placeholder")  # the factory checks the variable exists; nothing connects
    project = Path.cwd()
    lines = [json.loads(l) for l in Path(args.frames).read_text().splitlines() if l.strip()]
    cfg = next(l for l in lines if l.get("kind") == "config")
    attempts = [l for l in lines if l.get("kind") == "attempt"]
    spends = [l for l in lines if l.get("kind") == "spend"]
    rows, out = [], []
    for a in attempts:
        msgs = [l for l in lines if l.get("kind") == "message" and l["attempt"] == a["attempt"]]
        cls, where = classify(msgs)
        engine, _ = build_engine(project)
        outs = []
        for m in msgs:
            if m["after_close_stream"]:
                continue
            r = engine.engine_event_to_asr_event(json.dumps(m["message"]))
            if r is not None:
                outs.append(f"{type(r).__name__}({r.text!r})")
        commits = [o for o in outs if o.startswith("NewTranscript")]
        final = commits[-1] if commits else "None"
        late = [m["message"].get("event") for m in msgs if m["after_close_stream"] and m["message"].get("type") == "TurnInfo"
                and (m["message"].get("event") != "Update" or m["message"].get("transcript"))]
        eot = next((m["t_ms"] for m in msgs if not m["after_close_stream"] and m["message"].get("event") == "EndOfTurn"), None)
        rows.append((a, cls, where, outs, final, late, eot))

    out.append(header(f"cd examples/mantle-voice-banking-block-card-gpt && .venv/bin/python {sys.argv[0]} replay "
                      f"--frames {args.frames} --out {args.out}",
                      "offline replay of the recorded Flux messages through the installed "
                      "DeepgramASR.engine_event_to_asr_event; live capture started "
                      + (attempts[0]["started_utc"] if attempts else "-")))
    out.append(f"Flux URL built by Rasa's own engine: {cfg['url']}")
    out.append(f"frames {cfg['frame_ms']} ms, lead silence {cfg['lead_silence_s']} s, trailing silence {cfg['trail_silence_s']} s, "
               f"then CloseStream; messages after CloseStream are excluded from class and replay")
    for sc in (l for l in lines if l.get("kind") == "sweep_config"):
        out.append(f"set phase-sweep ({sc['command']}): the bare WAV only, leading silence stepped by one 20 ms frame "
                   f"from {sc['lead_silence_s'][0]} to {sc['lead_silence_s'][-1]} s (one 240 ms Flux audio window), "
                   f"{sc['repeats']} passes; everything else as above")
    for k, v in cfg["wavs"].items():
        out.append(f"  {k}: {v['text']!r} duration {v['duration_s']} s, speech_s {v['speech_s']}, sha256 {v['sha256']}")
    out.append("")
    out.append("attempt | set | lead silence s | wav text | class | transcripts in frames (before CloseStream) | EoT at ms (speech off at ms) | handler outputs | handler result | TurnInfo after CloseStream")
    for a, cls, where, outs, final, late, eot in rows:
        out.append(f"{a['attempt']:2d} | {a.get('set', 'main')} | {a.get('lead_silence_s', cfg['lead_silence_s'])} | {a['text']} | {cls} | {where} | {eot} ({a['speech_off_t_ms']}) | "
                   f"{', '.join(outs) or '-'} | {final} | {','.join(late) or '-'}")
    out.append("")
    sets = []
    for r in rows:
        k = (r[0].get("set", "main"), r[0]["wav"])
        if k not in sets:
            sets.append(k)
    for set_name, name in sets:
        sub = [r for r in rows if (r[0].get("set", "main"), r[0]["wav"]) == (set_name, name)]
        text = cfg["wavs"][name]["text"]
        leads = sorted({r[0].get("lead_silence_s", cfg["lead_silence_s"]) for r in sub})
        out.append(f"set {set_name}, {text!r}: {len(sub)} attempts (leading silence {leads[0]}-{leads[-1]} s)")
        for c in sorted({r[1] for r in sub}):
            out.append(f"  {c}: {sum(1 for r in sub if r[1] == c)}")
        none = [r for r in sub if r[4] == "None"]
        noupd = [r for r in sub if not r[1].startswith("A ")]
        out.append(f"  handler None: {len(none)}; handler NewTranscript: {len(sub) - len(none)}")
        out.append(f"  sequences without an Update transcript: {len(noupd)}; "
                   f"None set == no-Update set: {set(r[0]['attempt'] for r in none) == set(r[0]['attempt'] for r in noupd)}")
    sweep = [r for r in rows if r[0].get("set") == "phase-sweep"]
    if sweep:
        out.append("")
        out.append("phase-sweep by leading silence: handler results per pass")
        for lead in sorted({r[0]["lead_silence_s"] for r in sweep}):
            rs = [r for r in sweep if r[0]["lead_silence_s"] == lead]
            out.append(f"  {lead:.2f} s: " + ", ".join(f"{r[1][0]}->{'None' if r[4] == 'None' else 'NewTranscript'}" for r in rs))
    bare_all = [r for r in rows if r[0]["wav"] == BARE]
    if bare_all:
        none = {r[0]["attempt"] for r in bare_all if r[4] == "None"}
        noupd = {r[0]["attempt"] for r in bare_all if not r[1].startswith("A ")}
        out.append("")
        out.append(f"all {BARE} ('Yes.') attempts, both sets: {len(bare_all)}; no-Update sequences {len(noupd)}; "
                   f"handler None {len(none)}; None set == no-Update set: {none == noupd}")
        allr = rows
        none_a = {r[0]["attempt"] for r in allr if r[4] == "None"}
        noupd_a = {r[0]["attempt"] for r in allr if not r[1].startswith("A ")}
        out.append(f"all attempts, both WAVs and sets: {len(allr)}; no-Update sequences {len(noupd_a)}; "
                   f"handler None {len(none_a)}; None set == no-Update set: {none_a == noupd_a}")
    for sp in spends:
        out.append("")
        out.append(f"spend, set {sp.get('set', 'main')}: {sp['audio_s']} s of audio sent ({sp['wall_s']} s connection wall time); "
                   f"~{sp['usd_ledger_rate']} USD at the ledger's 0.0065/min, ~{sp['usd_regular_rate']} USD at the "
                   f"regular 0.0077/min, ~{sp['usd_regular_rate_on_wall_time']} USD at 0.0077/min on wall time")
    if spends:
        a_s = sum(sp["audio_s"] for sp in spends); w_s = sum(sp["wall_s"] for sp in spends)
        out.append(f"spend, total: {round(a_s, 2)} s audio, ~{round(a_s / 60 * 0.0065, 4)} USD (ledger rate), "
                   f"~{round(a_s / 60 * 0.0077, 4)} USD (regular rate), ~{round(w_s / 60 * 0.0077, 4)} USD (regular rate on wall time); cap {cfg['cap_usd']} USD")
    Path(args.out).write_text("\n".join(out) + "\n")
    print("\n".join(out))


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("probe")
    a.add_argument("--env", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--cap", type=float, default=0.30)
    c = sub.add_parser("sweep")
    c.add_argument("--env", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--repeats", type=int, default=2)
    c.add_argument("--cap", type=float, default=0.30)
    b = sub.add_parser("replay")
    b.add_argument("--frames", required=True)
    b.add_argument("--out", required=True)
    args = p.parse_args()
    if args.mode in ("probe", "sweep"):
        asyncio.run(probe(args))
    else:
        replay(args)


if __name__ == "__main__":
    main()
