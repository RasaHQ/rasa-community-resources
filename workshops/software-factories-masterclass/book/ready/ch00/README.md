# Ready code for chapter 0

Use [Chapter 0: Run the agent you will learn to build](../../00-run-the-finished-agent.md).
Keep this directory in a Git clone. The complete demo code and frozen dependency locks are in `demo/`; no sibling example checkout or private wheel is needed.

```bash
cd demo
make setup
make env
# Fill in your issued Rasa Developer Edition licence in .env with your editor.
make doctor
make run-scripted
```

Open http://127.0.0.1:8942/ and complete a source-backed journey. In another terminal, from this `ch00` directory:

```bash
python3 check_demo.py
```

Four available cards are required for success. Unavailable sources produce NOT DONE; a three-card replay is not completion. Scripted mode uses real Mantle and source tools but makes no model or voice request. Stop only your checkpoint with Ctrl-C or `make stop` in `demo/`.

`SOURCE.json` records the upstream source snapshot for maintaining this complete checkpoint. Only the copied README licence link is adjusted for its new location. Runtime credentials, environments, caches and generated models are not part of the source snapshot.
