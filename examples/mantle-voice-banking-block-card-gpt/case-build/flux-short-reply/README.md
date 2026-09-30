# Deepgram Flux short replies: probe, saved frames and replays

The build lost the caller's bare "Yes." in 4 of 10 live turns and heard every longer reply. This folder holds the evidence for the cause: Rasa's Flux handler `_DeepgramV2.parse_event` fills its transcript buffer only from `Update` messages. When Flux sends `StartOfTurn` and then `EndOfTurn` with no `Update` between them, the handler returns `None`, even though both messages carry the words.

Every command runs from `examples/mantle-voice-banking-block-card-gpt` in the project's `.venv` (rasa-pro 3.21.0.dev5). Apart from the capture, none of them needs a key or the network.

| File | What it shows |
|---|---|
| `flux-short-reply-probe.py` | Streams the build's caller WAVs to Flux through Rasa's own engine and saves every server message (`probe`, `sweep`; these need `DEEPGRAM_API_KEY`). `replay` feeds the saved messages back through the installed handler offline. |
| `flux-short-reply-frames.jsonl` | Every Flux server message from the 54 attempts on 2026-09-30, with request ids stripped. |
| `flux-short-reply-replay.txt` | The replay: 26 of the 54 sequences had no `Update`, and the handler returned `None` on exactly those 26. |
| `frames_turn_structure.py`, `frames-turn-structure.txt` | The message order and confidence of every attempt. |
| `handler_probe.py`, `handler-frame-replay.txt` | Hand-built frames through the handler, showing the three paths. |
| `patched_handler_replay.py`, `patched-handler-replay.txt` | The same 54 sequences through a one-line change: on `EndOfTurn` with an empty buffer, commit `EndOfTurn`'s own transcript. 26 `None` become 0, and no attempt commits twice. |
| `ga_3_20_1_handler_replay.py`, `ga-3-20-1-handler-check.txt`, `ga-3-20-1-handler-replay.txt` | The released rasa-pro 3.20.1 has the same `EndOfTurn` logic; its `StartOfTurn` returns `UserIsSpeaking(text="")`. Replayed, it also commits nothing on 26 of 54. <!-- rasa-version-ignore: the released handler, compared on purpose --> |
| `unheard_turns.py`, `unheard-turns-output.txt` | Flags caller turns that produced no user event in a run's `results.json`. |

```bash
.venv/bin/python case-build/flux-short-reply/flux-short-reply-probe.py replay \
  --frames case-build/flux-short-reply/flux-short-reply-frames.jsonl --out /tmp/replay.txt
cd case-build/flux-short-reply && ../../.venv/bin/python patched_handler_replay.py
pip download rasa-pro==3.20.1 --no-deps -d /tmp/rasa-3.20.1  # rasa-version-ignore: the released handler, compared on purpose
../../.venv/bin/python ga_3_20_1_handler_replay.py /tmp/rasa-3.20.1/rasa_pro-3.20.1-py3-none-any.whl flux-short-reply-frames.jsonl
```

The first line of each `.txt` file records the date and the exact command that produced it.
