# Note on edited local paths

On 2026-10-17 the file-system paths of the machine that ran these recordings were replaced with placeholders in two files: `drivers/run_one_codex_and_claude.sh` (the folder and virtual environment, originally on lines 3 and 4 and now on lines 4 and 5, became `MF_DIR` and `MF_VENV`; a third edit, a no-op loop turned into a comment, is described in `drivers/README.md`) and `codex-2026-10-15/codex-a1-block-card-2/decision.json` (the Python install prefix and a temporary-folder prefix in one recorded traceback became `<python>/` and `<tmp>/`). The driver therefore differs from what ran in three places in total (two path variables and the comment). Nothing else in the recorded runs was edited.

## Other recorded results in this repository

Eight `results.json` files under `examples/mantle-voice-banking-advisor-appointment-claude/`, `examples/mantle-voice-banking-dispute-claude/` and `examples/mantle-voice-payment-boundary-gpt/` (`case-build/results/`) recorded the absolute folder path of the machine that ran them inside Python tracebacks. In those files the folder prefix has been replaced by the placeholder `<build>/`; nothing else in the recorded results was edited. Read `<build>/` as the checkout of the example on the machine that ran it, not as part of any instruction.
