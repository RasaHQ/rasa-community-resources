"""Load the voice page in headless Chromium against a running agent and check one call.

    python3 shared/web/serve.py rasa &                  # page + relay to the agent on :5005
    uv run --with playwright python shared/web/check_page.py \\
        --wav shared/spec/caller-audio/aura-2-athena-en-627c5676d6dc.wav \\
        --text "Yes, please send it." --screenshot page.png

What it checks, from the page's own state (``window.cedarVoice``):

1. the WebSocket opened and the first frame was a handshake with a sample rate;
2. the greeting arrived as audio and its markers were acknowledged;
3. an audio round trip: Chromium's fake microphone plays the caller WAV
   (padded with silence so it starts after the greeting), the page streams it
   as {"audio"} frames, and the agent answers with a user event and audio;
4. a text round trip: {"text"} is sent and the agent answers with audio.

It prints a JSON summary and saves a screenshot. Needs Playwright
(``uv run --with playwright``); pass ``--chromium`` to use a browser already
on the machine instead of Playwright's download. Billed like any call: the
agent's model and speech vendor.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import wave
from pathlib import Path


def padded_wav(src: Path, lead_s: float, tail_s: float) -> Path:
    with wave.open(str(src)) as w:
        rate, pcm = w.getframerate(), w.readframes(w.getnframes())
    out = Path(tempfile.mkdtemp()) / "caller.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(lead_s * rate) + pcm + b"\x00\x00" * int(tail_s * rate))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--page", default="http://127.0.0.1:8765/")
    parser.add_argument("--wav", type=Path, help="caller audio for the fake microphone (16-bit mono WAV)")
    parser.add_argument("--lead-s", type=float, default=9.0, help="silence before the caller speaks")
    parser.add_argument("--text", default="Yes, please send it.")
    parser.add_argument("--screenshot", type=Path, default=Path("voice-page.png"))
    parser.add_argument("--chromium", default=None, help="path to a Chromium or Chrome binary")
    parser.add_argument("--timeout-s", type=float, default=90.0)
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    launch_args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                   "--autoplay-policy=no-user-gesture-required"]
    if args.wav:
        launch_args.append(f"--use-file-for-fake-audio-capture={padded_wav(args.wav, args.lead_s, 4.0)}%noloop")
    report: dict = {"page": args.page, "steps": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=launch_args, executable_path=args.chromium)
        page = browser.new_page(viewport={"width": 1000, "height": 1100})
        page.on("console", lambda m: report.setdefault("console", []).append(m.text) if m.type == "error" else None)
        page.goto(args.page)
        page.wait_for_function("window.cedarVoice !== undefined")
        if not args.wav:
            page.uncheck("#usemic")
        page.uncheck("#halfduplex")
        page.click("#connect")
        state = lambda: page.evaluate(  # noqa: E731
            "() => { const s = window.cedarVoice; return {handshake: s.handshake, rate: s.rate, relay: s.relay,"
            " sender: s.sender, framesSent: s.framesSent, audioChunksIn: s.audioChunksIn,"
            " audioSecondsIn: s.audioSecondsIn, markersIn: s.markersIn, markersAcked: s.markersAcked,"
            " lastLatency: s.lastLatency, closed: s.closedReason,"
            " users: s.events.filter(e => e.event === 'user').map(e => e.text),"
            " bots: s.events.filter(e => e.event === 'bot').map(e => e.text)}; }")

        def wait(cond, what: str) -> dict:
            deadline = time.monotonic() + args.timeout_s
            while time.monotonic() < deadline:
                s = state()
                if cond(s):
                    report["steps"][what] = "ok"
                    return s
                if s["closed"]:
                    break
                time.sleep(0.25)
            report["steps"][what] = "FAILED"
            return state()

        s = wait(lambda s: s["handshake"] is not None, "handshake")
        s = wait(lambda s: s["audioChunksIn"] > 0 and s["markersAcked"] > 0 and s["bots"], "greeting audio and markers")
        if args.wav:
            audio_before = s["audioSecondsIn"]
            s = wait(lambda s: len(s["users"]) >= 1 and len(s["bots"]) >= 2 and s["audioSecondsIn"] > audio_before + 1,
                     "audio round trip")
            time.sleep(3)
        users_before, audio_before = len(state()["users"]), state()["audioSecondsIn"]
        page.fill("#text", args.text)
        page.click("#send")
        s = wait(lambda s: len(s["users"]) > users_before and s["audioSecondsIn"] > audio_before + 1,
                 "text round trip")
        time.sleep(6)
        s = state()
        report["state"] = s
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(args.screenshot), full_page=True)
        report["screenshot"] = str(args.screenshot)
        page.click("#hangup")
        browser.close()
    print(json.dumps(report, indent=2))
    return 0 if all(v == "ok" for v in report["steps"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
