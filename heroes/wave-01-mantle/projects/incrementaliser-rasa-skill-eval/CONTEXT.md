# Rasa skill eval

Glossary for this evaluation harness. Implementation details live in CODEBASE.md.

## Language

**Mantle**:
Rasa Pro conversational engine used by the example agents in this project.
_Avoid_: CALM, rasa-open-source

**Rasano**:
Community Mantle banking example agent (`corpus/rasano`). Users greet it by name.
_Avoid_: the harness, the Mantle engine

**Personalization**:
Community Mantle example that seeds identity at session start and reuses it in `view_transactions`.
_Avoid_: a Rasano skill, a pattern grafted into Rasano

**Projection**:
Conversion of a native Mantle skill folder into an Agent Skills package (`SKILL.md`) for NVIDIA SkillEvaluator.
_Avoid_: rewrite, improve, train

**Reverse-merge**:
Copy of improved prose back onto native `skill.md` while keeping Mantle frontmatter.
Unknown `:::ordered_block` step keys such as `done_when` are stripped (not renamed to
`complete_when`). `REMERGE_SCHEMA` is part of the agent-tree stamp so resume rebuilds
poisoned copies. A failed `rasa train` also retries after this sanitizer, same as the
session-prose workaround.

**Layer A**:
Offline NVIDIA hygiene scores on projected copies before and after the improver.

**Layer B**:
Live task success on trained agent trees (native vs improved), crossed with actor model size.

**Arm**:
One side of a Layer B A/B: `native` or `improved` copy of an agent tree.

**Agent tree**:
A Mantle project copy under `runs/.../agents/<agent>/<model>/<arm>/` that can be trained and served.

**Improver pair**:
One skill that was projected, scored, rewritten, and re-scored. Layer A headline Δ uses only these.

**Agent core**:
Chat/tool model inside the live Mantle agent (`llm.agents`). The Layer B size factor.
_Avoid_: judge, improver, embeddings

**Improver**:
LLM that rewrites projected `SKILL.md` (`llm.improver`).

**NVIDIA scorer**:
SkillEvaluator CLI used for package quality and optional rubric. Not `llm.judge`.

**Embeddings**:
FAQ/reference indexing model used at `rasa train` for Rasano (`llm.embeddings`). Train plumbing, not a score.

**Weighted TSR**:
Per-repeat weighted mean of applicable assertion components; table cells average those scores.

**Strict TSR**:
Pass only when every applicable component on a repeat is 1.

**Tokens/task**:
Provider prompt+completion usage on live turns when present. Not dollars and not skill-doc length.

**Skill-doc length**:
Whitespace word count of projected `SKILL.md` before/after the improver.

**Rubric Eval**:
NVIDIA Tier 1 LLM-as-a-judge score on projected skills across qualitative criteria (clarity, boundaries, structure).

**`rasa train`**:
Compile a Mantle project into a runnable model artifact. Not LLM fine-tuning.

**Shareable report**:
Filled `runs/<id>/REPORT.md` from `docs/REPORT.md`. The main body is the evaluation write-up; extra DeepEval tables, rubric criteria, extra plots, improver delta, and inventory live in the Appendix. Numbers never go into `docs/REPORT.md`.

**Integration issue**:
A Mantle or rasa-pro failure observed while training or serving an agent tree. Recorded in `results.json` and the filled report with **Report this to Rasa**. Distinct from NVIDIA 429s or Ctrl+C, which are harness notes.

**Coverage unit**:
One planned Layer B actor or agent/model/arm recorded in `coverage.json` as pending/running/complete/skipped/failed.

**`eval-all`**:
The final cluster path. From-scratch Layer A (re-project, Kimi with writing-for-agents + unslop, NVIDIA T1/T2) then Layer B TSR then DeepEval. `sbatch job.sh` submits this for 48 hours. Completeness means scores exist, not that a CLI command ran.

**`resume-missing`**:
Command that clones an existing run folder and fills missing Layer A/B evaluations. Reuses saved on-disk improved skills without calling the improver LLM unless `--reimprove` or `--retry-degraded` is explicitly passed. Keeps already-projected `SKILL.md` (`preserve_projections`) unless `--reimprove`. DeepEval fills only skipped/missing metrics. Improved NVIDIA quality for `quality_delta.png` is read from hydrated `nvidia` rows when the resume score call returns no new `imp_results`.

**`run-all2`**:
Library command that seeds a new dated run from donated Layer A packages (`projected/` + `improved/` + improver rows, default `runs/zfiles`), rescoring NVIDIA locally and running Linux Layer B. Kimi is not called. Not the final cluster entrypoint. Do not use `eval-all --run-dir runs/zfiles` for this; that would skip completed Windows actors.

**NVIDIA-vs-Mantle mismatch**:
SkillEvaluator may demand coding-agent layout (`# Title`, `## Instructions`, `## Examples`, `folder_hierarchy`) that native Mantle `skill.md` cannot consume. Those headings stay on the projected copy. Completion criteria belong in instruction prose on the projected copy, not as new YAML step keys. If `rasa train` rejects the reverse-merged body after sanitizing unknown step keys, that is an integration issue with **Report this to Rasa**. NVIDIA-only deductions that never reach train stay in harness notes.

**Improver cache**:
`runs/.improver-cache/` keyed by schema `v3` plus writing-for-agents, unslop, and the projected `SKILL.md`. Schema-fail and near-noop rewrites are not cached. `--retry-degraded` also retries skills whose improved validate still has SCHEMA HIGH.

**DeepEval skip vs fail**:
Missing extra or missing transcripts is an unexecuted/skip stage. Metric API errors after transcripts exist are “DeepEval produced no scores”, never “unexecuted”. Coverage is `scored/expected` per metric, with **expected** taken from non-skipped TSR identities (not from whichever DeepEval rows happened to exist). `tool_correctness` alone (no LLM) does not make a DeepEval unit complete; `task_completion`, `answer_relevancy`, and `g_eval_tool_correctness` must have scores. DeepEval writes `deepeval/results.json` after each transcript.

**Judge backup**:
Primary DeepEval judge is `nvidia/nemotron-3-super-120b-a12b`. After persistent 429/503/410 **or** a GEval schema mismatch (retry once on the same model first) it switches to `llm.judge.backup_provider` / `backup_model` (OpenAI `gpt-4.1-mini` via `OPENAI_API_KEY`) and keeps waiting rather than dumping the rest of the matrix as skips. Rate-limit retries do not use the old 3-attempt cap; `eval.judge_max_retries` bounds the outer loop. Setting `llm.judge.provider: openai` uses OpenAI as the only judge.

**SkillEvaluator models**:
`nvidia.rubric_model` and `nvidia.embedding_model` pin live NIM endpoints (`nemotron-3-super-120b-a12b`, `nemotron-3-embed-1b`) via `SKILL_EVAL_LLM_MODEL` / `SKILL_EVAL_EMBEDDING_MODEL`. Defaults `nemotron-3-nano-30b` and `nv-embed-v1` are EOL (HTTP 410). A rubric/T2 command that ran with a null score is incomplete. Rubric scores come from `rubric_eval.overall_score` and `checks`; when overall is null, a mean of criterion scores (0–10 × 10) is used. A below-`--min-score` CLI exit is still a recorded score. JSON-extract failures that SkillEvaluator labels `llm_unavailable` are incomplete judge output, not EOL; resume retries after clearing the report dir, using the DeepEval backup judge env. T2 pair counts include nested `SIMILARITY` findings when the top-level report failed. Layer A hydrates those JSON files into `results.json` before invoking the CLI again.

**Completeness**:
A Layer A NVIDIA command is successful only when it is not skipped **and** the score it is supposed to produce is present (quality_score / rubric_score / T2 pair count parsed from JSON, never JSON file count and never CLI exit 0). Progress percent uses `complete` units only. Layer A progress requires quality+validate and, when a provider key exists, rubric scores on both arms. Seed overwrites stale `complete` from disk inference.

**Progress manifest**:
`runs/<run>/progress.json`, the atomic, resume-aware checklist used by Rich and
optional MLflow views. It covers Layer A skills, Layer B scenario repeats,
DeepEval transcripts, and report finalization. Only `complete` units count
toward “all numbers available”; failed and skipped units remain visible gaps.

**Progress observers**:
The local Rich bars and optional MLflow tracker consume the same progress
manifest. Detailed Loguru output stays in `pipeline.log` and `agent_eval.log`
while interactive bars are active. MLflow is enabled only when its optional
extra and `MLFLOW_TRACKING_URI` (or `--tracking-uri`) are provided.

**Safe stop**:
Ctrl+C once, followed by waiting for cleanup. Completed units and observations
are durable; the in-flight unit may repeat on resume. `eval-all` finalizes a
partial report in cleanup, while an interrupted `resume-missing` may require
`uv run report --run-dir <run>`. Never remove the run directory before resume.

**Owned llama**:
A llama-server child started by this process. The harness keeps the PID and log; leftover port listeners are recovered only after that child is gone. On this cluster the binary is a CUDA `llama.cpp` build (`-ngl 99`, optional `-fa on`) serving one Q4_K_M GGUF at a time. Listener recovery uses `ss`/`lsof` on Linux and `netstat` on Windows.

**GPU cluster (A40)**:
Login nodes have no GPU. Layer B llama-server must run under Slurm (`sbatch job.sh`, or `srun -p gpu --gres=gpu:a40:1`). `job.sh` currently submits `resume-missing --source-run runs/heroes_eval_20260920_105819 --no-progress` on one A40 for 48 hours (retry hollow rubric, skip complete TSR, fill DeepEval LLM scores, rewrite plots). From-scratch is `uv run eval-all --no-fetch --no-progress`. Build llama.cpp with `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86`. One GGUF loaded at a time; 30B Q4 plus 8k KV fits 48GB. Improver stays on NVIDIA NIM. DeepEval uses NVIDIA then the configured OpenAI backup.

**W&B tracking**:
Optional hosted progress at wandb.ai. Enabled when `WANDB_API_KEY` is set (`uv sync --extra tracking`). The run URL is logged at start. MLflow remains optional via `MLFLOW_TRACKING_URI`.
