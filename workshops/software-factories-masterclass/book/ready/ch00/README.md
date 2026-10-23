# Ready code for chapter 0

Follow [Chapter 0: Run the agent you will learn to build](../../00-run-the-finished-agent.md) from a Git clone.

```bash
cd demo
make setup
make env
# Fill in your issued Rasa Developer Edition license with your editor.
make doctor
BRIEFING_RECORDED=1 make run-scripted
```

At http://127.0.0.1:8942/, say “United 1162 to EWR”, then “The 6 pm meeting tomorrow”. Every card says REPLAY, with an initial 90-minute transfer. Ask “Allow 30 minutes to get into town”. In another terminal, from this `ch00` directory:

```bash
python3 check_demo.py --recorded --transfer-minutes 30
```

It fails before that revision and passes afterward. You can choose 120 instead. This uses the real Mantle/MCP/Core workflow with recorded source references and a fixed clock; no live source, model or voice request is needed after installation. There is no substitute Inspector or card renderer. The canonical timeline helper recomputes only your meeting/transfer plan. The aircraft, weather and reference-rate observations stay recorded.

`recorded-journey.json` contains four references captured through the canonical briefing Jobs/PublicSourcesRunner on 22 October 2026, without private runtime handles. Playback marks every reference REPLAY. The license is still needed by Mantle. Stop only your checkpoint with Ctrl-C or `make stop` in `demo/`.

`SOURCE.json` records the upstream snapshot and declared chapter-only adapters. The two small runtime adjustments select the recorded adapter and announce its mode; public-source mode remains the optional extra. Environments, credentials, caches and generated models are not source.
