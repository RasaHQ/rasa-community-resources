# Run Manifest: `heroes_eval_20260920_182120`

This directory contains the slimmed evaluation snapshot for `heroes_eval_20260920_182120` (assessed on `2026-09-20` against `rasa-pro==3.20.0.dev6`).

The full, unslimmed snapshot (`5.1 MB`, 138 files) remains archived at [`incrementaliser/rasa-community-resources@heroes-wave-01-full-snapshot`](https://github.com/incrementaliser/rasa-community-resources/tree/heroes-wave-01-full-snapshot/heroes/wave-01-mantle/projects/incrementaliser-rasa-skill-eval/runs/heroes_eval_20260920_182120).

## Committed in this branch

- [`REPORT.md`](REPORT.md): Filled evaluation report with Layer A (NVIDIA SkillEvaluator) and Layer B (live Mantle Task Success Rate and DeepEval judge) tables, statistical tests, and Mantle engine findings.
- [`IMPROVER_DELTA.md`](IMPROVER_DELTA.md): Per-skill Layer A quality scores, word counts, and rewrite modes before and after the improver pass.
- `plots/*.png` (27 figures): Figures referenced directly by [`REPORT.md`](REPORT.md), kept here so the report renders inline on GitHub.
- `improved/<agent>/<skill>/SKILL.md` (10 files): Unique LLM-rewritten skill documents produced on `2026-09-20` by `nvidia/moonshotai/kimi-k3` (`moonshotai/kimi-k3`) using Matt Pocock's `writing-for-agents` prompt and the local `unslop` pass. Because external LLM sampling is non-deterministic across runs, these 10 files preserve the exact rewritten prompt bodies evaluated in Layer A and reverse-merged into Layer B:
  - `improved/personalization/default-session-start/SKILL.md`
  - `improved/personalization/view-transactions/SKILL.md`
  - `improved/rasano/add-payee/SKILL.md`
  - `improved/rasano/block-card/SKILL.md`
  - `improved/rasano/default-session-start/SKILL.md`
  - `improved/rasano/human-handoff/SKILL.md`
  - `improved/rasano/intro/SKILL.md`
  - `improved/rasano/list-payees/SKILL.md`
  - `improved/rasano/remove-payee/SKILL.md`
  - `improved/rasano/transfer-money/SKILL.md`

## Omitted from this branch (regenerable or duplicate)

All omitted artifacts remain available on the archive branch [`heroes-wave-01-full-snapshot`](https://github.com/incrementaliser/rasa-community-resources/tree/heroes-wave-01-full-snapshot/heroes/wave-01-mantle/projects/incrementaliser-rasa-skill-eval/runs/heroes_eval_20260920_182120):

- `projected/`: Deterministic output of `uv run fetch-corpus` followed by the `rasa_skill_eval.projector` package converter.
- Unchanged `improved/` skills (`rasano/banking-faq`, `rasano/check-balance`, `rasano/goodbye`): These 3 skills kept their projected `SKILL.md` unchanged when the LLM rewrite gate rejected the candidate (recorded as `mode: failed` in [`IMPROVER_DELTA.md`](IMPROVER_DELTA.md)).
- Non-`SKILL.md` files under `improved/` (`config/mantle.yml`, `config/memory.yml`, `config/responses.yml`, `scripts/tools.py`, `references/*`): Byte-identical copies of the deterministic projection and upstream corpus files.
- `results.json`, `progress.json`, `coverage.json`: Raw machine-readable run state and per-repeat score dumps whose aggregate tables and findings are already rendered in [`REPORT.md`](REPORT.md) and [`IMPROVER_DELTA.md`](IMPROVER_DELTA.md).
- `HEROES_REPORT.md`: Condensed summary whose tables and `rasa.train_failed` records are already included in [`REPORT.md`](REPORT.md).

## Rebuilding omitted files

From `heroes/wave-01-mantle/projects/incrementaliser-rasa-skill-eval/`:

1. Install dependencies and fetch the pinned corpora:
   ```bash
   uv sync --group dev
   uv run fetch-corpus
   ```
2. Rebuild `projected/` and score Layer A (requires `NVIDIA_API_KEY` and the `skillevaluator` CLI):
   ```bash
   uv run skill-eval --run-dir runs/heroes_eval_20260920_182120
   ```
   When `improved/<agent>/<skill>/SKILL.md` is already present in `--run-dir`, the harness reuses those saved rewrites unless `--reimprove` is passed.
3. Run live Layer B agent training and scenario evaluation (requires `RASA_LICENSE` for `rasa-pro==3.20.0.dev6` plus configured actor endpoints or local GGUF servers):
   ```bash
   uv run agent-eval --run-dir runs/heroes_eval_20260920_182120
   ```
4. Regenerate `REPORT.md` and `plots/` from a populated run directory:
   ```bash
   uv run report --run-dir runs/heroes_eval_20260920_182120
   ```

Note: Running the pipeline from scratch into a new run directory calls external LLM endpoints (`nvidia/moonshotai/kimi-k3`, `nvidia/nemotron-3-super-120b-a12b`, and live actor models) and will not reproduce the `2026-09-20` prose or stochastic transcripts bit-for-bit.

## Provenance

- **Run ID:** `heroes_eval_20260920_182120`
- **Assessed on:** `2026-09-20`
- **Engine pin:** `rasa-pro==3.20.0.dev6`
- **Improver model:** `nvidia/moonshotai/kimi-k3`
- **DeepEval judge model:** `nvidia/nemotron-3-super-120b-a12b`
- **Embeddings model:** `nvidia/nemotron-3-embed-1b`
- **Pinned corpora (`corpus/pins/*.sha`):**
  - `rasano`: `https://github.com/RasaHQ/rasa-community-resources.git` (`examples/mantle-voice-banking-skills`) at commit `5070107f73d4048e86f876f1f42878e2244b2bb5`
  - `personalization`: `https://github.com/RasaHQ/rasa-community-resources.git` (`patterns/session-start-personalization`) at commit `5070107f73d4048e86f876f1f42878e2244b2bb5`
  - `writing_for_agents`: `https://github.com/mattpocock/skills.git` (`writing-for-agents`) at commit `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`
