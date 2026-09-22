# Rasa Mantle skill eval

Score Mantle example skills with NVIDIA SkillEvaluator **only after converting them to Agent Skills packages**. Measure `writing-for-agents` + unslop rewrites on those copies. Reverse-merge prose into Rasano and personalization copies; report weighted TSR across `llm.agents`. Pin rasa-pro `3.20.0.dev6`, engine `mantle`.

Native `skill.md` is not SkillEvaluator input. Do not point the CLI at `corpus/*/skills/`.

## Layout

- `config.yaml`. Pin, corpora, NVIDIA checks, `llm.improver/agents/judge/embeddings`, `eval.tsr_weights`, CUDA llama knobs (`llama_n_gpu_layers`, `llama_flash_attn`, `llama_parallel`, `llama_threads`). No secrets.
- `.env`. `NVIDIA_API_KEY`, `RASA_LICENSE`, optional OpenAI/Anthropic, `LLAMA_BASE_URL`, `LLAMA_SERVER_EXE`, optional `WANDB_API_KEY` / `WANDB_PROJECT`.
- `models/`. Local Q4 GGUFs (gitignored). `local_llm.py` downloads/starts one actor for Layer B; `scripts/download_local_llms.py --tier lfm|8b|30b|all` for a manual fetch.
- `llama.cpp/`. Gitignored CUDA checkout/build. `llama.cpp/build/bin/llama-server` is the Linux GPU binary.
- `src/rasa_skill_eval/`. Library.
  - `llm/`. ChatClient: nvidia / local llama.cpp / openai / anthropic. `backup_endpoint` honors `backup_provider` (OpenAI key + api.openai.com) independently of the primary provider.
  - `skill_io.py`. Frontmatter parse for `skill.md` and `SKILL.md`.
  - `rasa_static.py`. Mantle inventory.
  - `scope.py`. skill-local / project-global / engine-managed / coding-agent.
  - `projector.py`. Mantle → Agent Skills conversion. New runs wrap the body with `# Title`, `## Instructions`, and `## Examples` (examples from matching eval scenarios or a non-invented placeholder). Sidecar JSON lives at `projected/<corpus>/.sidecars/<skill>.json`, not inside the skill root.
  - `nvidia_runner.py` / `nvidia_llm.py`. T1 quality+validate+rubric, T2 similarity. CLI `cwd` is a temp `skills/<name>/` tree (NVIDIA packaging, not Mantle layout). `similarity-check --type skill` plus `--model` from `nvidia.embedding_model`; chat/embed models also pinned through `SKILL_EVAL_LLM_MODEL` / `SKILL_EVAL_EMBEDDING_MODEL`. T2 pair counts are parsed from nested JSON findings even when `overall_status` is failed, never `unique_json_file_count`. Rubric overall comes from `rubric_eval.overall_score` and `checks`; criterion-only JSON yields a mean overall. A below-bar CLI exit still records the score. Null rubric/quality or EOL 410 with no score is `skipped=True` (incomplete). JSON-extract `llm_unavailable` is retried with `llm.judge` backup env after clearing the report dir. `hydrate_nvidia_from_reports()` re-parses `nvidia/**/*.json` before the CLI. SCHEMA HIGH parsed from validate JSON.
  - `improver.py`. Pure LLM rewriting via writing-for-agents + unslop with primary model and NIM backup (`meta/llama-3.1-70b-instruct`). Cache schema `v3` under `runs/.improver-cache/`; schema/noop gates skip caching. Degradation retry also fires on SCHEMA HIGH. Skill-doc word counts on ImproverDelta. Completion criteria go in instruction prose, not new `:::ordered_block` YAML keys.
  - `remerge.py`. Improved structured prose back onto native `skill.md` (headings kept). Strips unknown ExecuteStep keys (`done_when`). Session-prose and unknown-step workarounds after a failed train, not during Layer A. `REMERGE_SCHEMA` is hashed into the agent-tree stamp. Heading train failures become integration issues (**Report this to Rasa**).
  - `deepeval_judge.py`. Optional judge on transcripts using `config.llm.judge` via a ChatClient adapter that honors DeepEval `schema` (never return a bare `str` when a schema was requested; GEval `score`/`reason` JSON is coerced). `LLMTestCase` always gets `tools_called` / `expected_tools` (empty lists, never `None`). `ToolCorrectnessMetric` has no `model=`; GEval is constructed with `evaluation_params`. Per-metric resume keeps scored rows; schema mismatch retries once then 429/503/410/schema switch to `llm.judge.backup_provider`/`backup_model` (OpenAI by default). Rate-limit retries keep waiting up to `eval.judge_max_retries`. Results are checkpointed after each transcript. Per-metric failures are `skipped=True`, not silent complete.
  - `pipeline.py`. `run_pipeline()` Layer A only (Rasano + personalization). Inventory `skill_id` is `{corpus}/{folder}` so both `default_session_start` skills survive. Completeness uses `nvidia_command_successful`. Hydrates on-disk NVIDIA reports before scoring. `_apply_delta_quality` sets `improver.improved_quality` from the current score call, then falls back to hydrated `nvidia` `#improved` quality-check rows so resume cannot leave `quality_delta.png` hollow. `skip_improver` / `preserve_projections` support `run-all2` (no Kimi, no re-project of donated packages). `retry_incomplete` re-runs hollow NVIDIA commands. `seed_imported_layer_a()` copies `projected/` + `improved/` + improver rows only.
  - `cli.py`. `fetch-corpus` / `skill-eval` / `agent-eval` / `report` / `eval-all` / `resume-missing` / `run-all2`. Cluster entrypoint is `eval-all`. `--retry-degraded` is on skill-eval, eval-all, and resume-missing. `resume-missing` sets `preserve_projections=True` unless `--reimprove`. `run-all2 --source-run runs/zfiles` (default) seeds a new `run_all2_*` folder; do not `eval-all --run-dir runs/zfiles`.
  - `tsr.py` / `scenarios.py` / `agent_eval.py` / `rasa_live.py` / `tracker_parse.py` / `local_llm.py` / `proc.py` / `persist.py`. Factorial Layer B: model × agent × arm. `local_llm.py` owns llama-server (retained PID, per-actor logs under `runs/<run>/llama/`, dual wall/monotonic startup deadline, process-tree kill). Launch args include `-ngl` from `eval.llama_n_gpu_layers` (99 on the A40), optional `-fa on` when the binary supports it, `--parallel 1`, and 8192 context. Linux spawn uses `start_new_session` and `killpg` so leaked `uv run rasa` children do not hold ports. Linux stale listeners use `ss -ltnp` then `lsof`; Windows still uses `netstat`. All six actors (`lfm-1.2b`, `lfm-2.6b`, `llama-8b`, `nemotron-8b`, `muse-30b`, `gemma4-31b`) are local GGUF catalog rows. Improver/judge/embeddings stay on NVIDIA by default. DeepEval may switch to `llm.judge.backup_provider: openai`. Stage timeouts live on `eval.*` in `config.yaml` (`max_retry_after_sec: 300`, `judge_max_retries: 12`). A scenario has one total deadline; consecutive turn timeouts restart Rasa and trip a circuit breaker. `--run-dir` resumes: `coverage.json` plus identity merge; completed actors/arms/repeats are skipped when the eval hash still matches. Shared `runs/.venv-cache/<lock-hash>/` and `runs/.train-cache/<agent>/<arm>/<fingerprint>/`. `tools: []` is a no-tool assertion; tool order, allowlists, arguments, confirmation-before-action, `pin_fact`/`response_contains`, and grounded/refusal text are scored. Fixtures load only from `tsr/observations/<agent>/<model>/<arm>/`. Sweeps leftover `${OPENAI_API_KEY}` before train. DeepEval runs once at the end of Layer B and merges into `deepeval/results.json`.
  - `tracking.py`. Optional `MlflowTracker` (`MLFLOW_TRACKING_URI`) and `WandbTracker` (`WANDB_API_KEY`). Both are progress observers; W&B is the hosted dashboard for this cluster.
  - `stats.py` / `plots.py` / `finalize.py` / `report.py`. Paired native/improved populations only, CIs, skill-paired Spearman pooled across models (per-slice ρ on `by_model`). Plots: TSR, quality, `rubric_delta.png`, NVIDIA-vs-TSR, tokens, and DeepEval (`deepeval_by_metric.png`, `deepeval_by_model.png`, `deepeval_<metric>_by_model.png`, `deepeval_by_scenario.png`, `deepeval_by_model_size.png`, `deepeval_vs_tsr.png`). Titles include `n=scored/expected` with expected from planned TSR identities; skipped/`None` is a gap, not 0. DeepEval/rubric axes include every planned actor/scenario/skill even when one arm is still hollow. The filled `REPORT.md` main body is the evaluation write-up (six overall plots; TSR/tokens/task-completion tables). Extra DeepEval rows, Spearman, rubric criteria, extra plots, improver delta, and inventory go in the Appendix. Reports list configured actors separately from actors with live TSR. Dual Layer B headlines: repeat-pooled `tsr_weighted` vs equal-weight-per-model `layer_b_total`. NVIDIA SCHEMA HIGH and donated-run Kimi skip land in harness notes; train-breaking dual-format issues are integration issues.
  - `corpus.py`. Sparse git fetch. Vendors writing-for-agents into `.cursor/skills/`.
- `data/eval/scenarios/{rasano,personalization}/`. Assertion specs.
- `docs/REPORT.md`. Committed report template with placeholders. Filled copies only under `runs/`. Extra DeepEval/rubric/inventory tables go in the Appendix.
- `CONTEXT.md` / `AGENTS.md`. Glossary and short agent notes.
- `corpus/pins/*.sha`. Fetched commit pins. Clones are gitignored.

## Commands

```powershell
uv sync --group dev
uv run pytest
uv run ruff check src tests scripts
uv run fetch-corpus
uv run skill-eval
uv run agent-eval
uv run report
uv run eval-all
uv run run-all2 --no-fetch
sbatch job.sh
```

SkillEvaluator is an isolated uv tool on Python 3.13.

## Conventions

- Dated outputs: `runs/<name>_YYYYMMDD_HHMMSS/`
- Improver cache: `runs/.improver-cache/` (gitignored with `runs/*`). `--reimprove` busts it. Schema `v3` hashes writing-for-agents + unslop + projection stamps. Schema-fail and noop rewrites are not cached.
- Resume: `coverage.json` + identity-merged `results.json`. Changing `eval.*`, actors, or scenario files invalidates skip. `--retry-degraded` also retries SCHEMA HIGH improved skills.
- `eval-all` writes a partial `REPORT.md` on interrupt or crash. This is the final cluster job (`sbatch job.sh`, 48h, `--no-fetch --no-progress`). Completeness means quality/rubric/T2/DeepEval **scores exist**.
- `run-all2 --no-fetch --source-run runs/zfiles` reseeds Layer A packages into a new `run_all2_*` folder, rescores NVIDIA, and runs Linux Layer B. It does not call Kimi and does not copy Windows `agents/` or `coverage.json`. Keep it as a donated re-score path; do not use it as the final run.
- Do not edit `corpus/` by hand. Re-fetch.
- Do not train Mantle on `runs/*/improved` projected folders. Use `runs/*/agents/...` after reverse-merge.
- Stable PyPI `rasa-pro` has no Mantle engine.
- Tools import `rasa.mantle.tools`. LLM config is `llm.model_group` plus `model_groups`.
