# Rasa Mantle skill evaluation

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/heroes-wave-01-mantle-projects-incrementaliser-rasa-skill-eval/devcontainer.json)

This cohort snapshot installs its own locked Rasa version; it does not track catalog upgrades.

- **You need:** nothing for the first command, which needs no license and no network. Later steps use the free Rasa Developer Edition license and the keys named: `RASA_LICENSE`, `NVIDIA_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, saved once as personal Codespaces secrets ([how](../../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `uv run --locked --no-sync pytest && uv run --locked --no-sync ruff check src tests scripts`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the offline unit suite and lint checks finish. Model scoring and licensed training are separate steps below; no evaluation starts automatically.
<!-- codespaces:end -->

```text
Author:        Arash Ashrafzadeh
Wave:          wave-01-mantle
Assessed on:   2026-09-20
Assessed by:   Arash Ashrafzadeh
Verified with: rasa-pro 3.20.0.dev6, Python 3.12+, uv
Audience:      People scoring Rasa Mantle skills and measuring live TSR
Time:          30 minutes to install and read the filled report; hours to hours for a full eval
```

Score Mantle example skills with [NVIDIA SkillEvaluator](https://docs.nvidia.com/skills/skillevaluator/quickstart) **after converting them to Agent Skills packages**, improve those copies with Matt Pocock’s `writing-for-agents` (plus unslop), then measure **weighted task success rate** and tokens/task on live Rasano and personalization agents across actor models listed in `config.yaml`.

**Native Mantle** `skill.md` **is not SkillEvaluator input.** Every NVIDIA number is on a projected copy. The pin is `3.20.0.dev6` in `config.yaml`.

The evaluation write-up template is [docs/REPORT.md](docs/REPORT.md). The filled snapshot from the last successful run is [runs/heroes_eval_20260920_182120/REPORT.md](runs/heroes_eval_20260920_182120/REPORT.md) (plots, [`IMPROVER_DELTA.md`](runs/heroes_eval_20260920_182120/IMPROVER_DELTA.md), and unique rewritten `SKILL.md` files sit beside it; see [`runs/heroes_eval_20260920_182120/MANIFEST.md`](runs/heroes_eval_20260920_182120/MANIFEST.md) for the reproducible boundary and the [`heroes-wave-01-full-snapshot`](https://github.com/incrementaliser/rasa-community-resources/tree/heroes-wave-01-full-snapshot/heroes/wave-01-mantle/projects/incrementaliser-rasa-skill-eval/runs/heroes_eval_20260920_182120) archive branch for raw JSON dumps and deterministic projections). Extra DeepEval tables, rubric criteria, and run inventory live in that file's Appendix.

The root `agent.yml` / `skills/` tree is a **smoke Mantle agent** so catalog CI can `validate_project` this folder. The evaluation work lives in `src/rasa_skill_eval/`.

## Codespaces integration status

The configuration installs this contribution's own lock and checks its smoke
agent, then runs `pytest` and `ruff check src tests scripts`, as required by
its project instructions. These are the first offline checks; no model
scoring, corpus fetch, model download, training or remote tracking starts
automatically. They do not need provider keys.

The September assessment and published results above are the contributor's
historical report, retained with its original source and assets. They are not
new results from this integration. The [selected integration container run](https://github.com/matorclawson/rasa-community-resources/actions/runs/43108270451)
on initial head 70b56c50 installed the locked SDK, passed project validation,
passed all 207 unit tests and passed Ruff. This is an offline integration
receipt; it does not reproduce the stored model scores or establish current
provider access. The PR's own upstream checks remain separate.

Full evaluation requires the separately installed NVIDIA SkillEvaluator CLI,
the fetched corpus, configured model endpoints and their account keys. Local
GGUF evaluation also needs its external model files and suitable hardware.
Those dependencies are not installed by this Codespace. Read the commands
below before starting any step that calls a model or downloads data.

## Install

1. Python 3.12 and [uv](https://docs.astral.sh/uv/).
2. Copy env and set keys:

```powershell
copy .env.example .env
# NVIDIA_API_KEY — SkillEvaluator + NIM chat/embeddings
# RASA_LICENSE — required for uv run agent-eval (rasa train)
```

1. Install this package:

```powershell
uv sync --group dev
```

1. Install SkillEvaluator as a **separate** uv tool on Python 3.13 (not this venv):

```powershell
uv tool install --python 3.13 "skillevaluator[all] @ git+https://github.com/NVIDIA/SkillEvaluator.git"
```

1. This package pins `rasa-pro==3.20.0.dev6` (needed for catalog `validate_project`). Live Layer B still trains **copies** under `runs/.../agents/`, not this smoke tree.

Optional: `uv sync --extra judge` for DeepEval (secondary to assertion TSR).

Optional: `uv sync --extra tracking` for remote MLflow progress monitoring.

## Reproduce

1. Edit `llm.agents` in [config.yaml](config.yaml) to choose actor model ids/sizes.
2. Unit checks: `uv run pytest`
3. Fetch corpora: `uv run fetch-corpus`
4. Layer A (project NVIDIA skeleton, NVIDIA score, Kimi improve, re-score): `uv run skill-eval`
5. Layer B (train + scenarios; needs `RASA_LICENSE`): `uv run agent-eval`
6. Fill run report: `uv run report`
7. Or one dated folder from scratch: `uv run --extra judge eval-all` (re-project, Kimi, NVIDIA T1/T2, live TSR, DeepEval). On the GPU cluster: `sbatch job.sh` (48h, `--no-fetch --no-progress`). Completeness means scores exist, not that a CLI exited 0.

Outputs land in `runs/heroes_eval_YYYYMMDD_HHMMSS/` (`results.json`, `REPORT.md`, `plots/`). Failed train leaves TSR as `n/a` in that run report; git keeps the template without numbers.

To preserve a prior run and retry only its missing evaluations (reusing saved improved skills without re-calling the improver LLM):

```powershell
uv run --extra judge resume-missing --source-run runs/heroes_eval_20260920_105819
```

The source folder is never edited. The command writes a new dated run, reuses on-disk projected and improved `SKILL.md` files, completes missing Layer A and Layer B evaluations, fills skipped DeepEval metrics, and rebuilds the report and plots from the full planned matrix. Set `OPENAI_API_KEY` when `llm.judge.backup_provider` is `openai`. To explicitly force re-improving skills with the LLM, pass `--reimprove` (all skills) or `--retry-degraded` (only skills marked degraded, including remaining SCHEMA HIGH).

To rescore donated Layer A packages (default `runs/zfiles`) on Linux without calling Kimi:

```powershell
uv run run-all2 --no-fetch --source-run runs/zfiles
```

That writes `runs/run_all2_YYYYMMDD_HHMMSS/`, copies `projected/` and `improved/` only, reruns NVIDIA quality/validate locally, reverse-merges onto a Linux corpus tree, and runs Layer B. Keep this for donated re-scores; the final cluster path is `eval-all`. Do not `eval-all --run-dir runs/zfiles` (it would skip completed Windows actors). Do not copy Windows `agents/` venvs.

## Monitor a long run

Interactive eval commands show stable Rich progress bars for Layer A, Layer B,
DeepEval, and report generation. Detailed messages do not scroll through the
bars: they remain in the run's `pipeline.log` and `agent_eval.log`. The durable
`progress.json` is the source for all progress views; `results.json` remains the
canonical evaluation result.

Inspect the same manifest in another terminal:

```powershell
uv run progress --run-dir runs/heroes_eval_YYYYMMDD_HHMMSS --watch
```

Use `--no-progress` on an eval command in a non-interactive environment. To
publish progress to Weights & Biases (recommended) set `WANDB_API_KEY` and
`WANDB_PROJECT` in `.env`, then `uv sync --extra tracking`. The run URL is
logged at start; open it while logged into wandb.ai. Optional MLflow remains
available via `MLFLOW_TRACKING_URI` or `--tracking-uri`.
Only units marked `complete` contribute to the percentage. Failed and skipped
units therefore leave a visible gap where a report number is still unavailable.
The report is final only when the Finalize bar and `report:finalize` unit are
complete.

## Stop and resume safely

Press **Ctrl+C once**, then wait for the command to exit and finish its cleanup.
Completed Layer A skills, Layer B scenario rows, transcripts, coverage, and
integration issues are already persisted. The unit executing at the instant of
the stop may need to run again.

Keep the entire `runs/heroes_eval_.../` directory. Resume that directory with
the applicable command:

```powershell
uv run skill-eval --run-dir runs/heroes_eval_YYYYMMDD_HHMMSS
uv run agent-eval --run-dir runs/heroes_eval_YYYYMMDD_HHMMSS
uv run report --run-dir runs/heroes_eval_YYYYMMDD_HHMMSS
```

`eval-all` attempts to write a partial report during its Ctrl+C cleanup.
`resume-missing` preserves completed work but may need the explicit `report`
command after interruption. Do not force-kill the process or delete the run
folder if you intend to resume.

## LLM providers

| Role       | Config           | Purpose                                       |
| ---------- | ---------------- | --------------------------------------------- |
| Improver   | `llm.improver`   | Rewrites projected `SKILL.md`                 |
| Actors     | `llm.agents`     | Live Mantle chat/tool models (Layer B factor) |
| Judge      | `llm.judge`      | Optional DeepEval only                        |
| Embeddings | `llm.embeddings` | Rasano FAQ index at `rasa train` (held fixed) |

| `provider`  | Base URL                                                       | Key                 |
| ----------- | -------------------------------------------------------------- | ------------------- |
| `nvidia`    | `https://integrate.api.nvidia.com/v1`                          | `NVIDIA_API_KEY`    |
| `local`     | Per-agent `base_url` in `config.yaml` (else `$LLAMA_BASE_URL`) | `LOCAL_LLM_API_KEY` |
| `openai`    | `https://api.openai.com/v1`                                    | `OPENAI_API_KEY`    |
| `anthropic` | Anthropic Messages API                                         | `ANTHROPIC_API_KEY` |

Default Layer B actors: six local Q4_K_M GGUFs, one CUDA llama-server at a time (`eval.llama_n_gpu_layers: 99`): LFM 1.2B `:8082`, LFM 2.6B `:8081`, Llama 3.1 8B `:8083`, Nemotron Nano 8B `:8084`, Muse Glimmer 30B `:8085`, Gemma 4 31B-it `:8086`. Context is 8192. Improver (Kimi K3) stays on NVIDIA. Judge is Nemotron 3 Super 120B with backup `meta/llama-3.1-70b-instruct`. SkillEvaluator rubric/T2 use the same Super 120B chat model and `nvidia/nemotron-3-embed-1b`. Larger NIM actors remain commented in `config.yaml`.

`uv run agent-eval` / `eval-all` download missing GGUFs if needed, start **one** local llama-server at a time (to keep CPU RAM in check), and stop those servers when the local actors are done. Manual start/stop:

```powershell
uv run python scripts/download_local_llms.py --tier all
uv run python -m rasa_skill_eval.local_llm start lfm-1.2b
uv run python scripts/smoke_local_llm.py --base-url http://127.0.0.1:8082/v1 --model LFM2-1.2B
uv run python -m rasa_skill_eval.local_llm stop
```

Set `LLAMA_SERVER_EXE` in `.env` to the CUDA `llama-server` (on this cluster: `llama.cpp/build/bin/llama-server`). Windows AutoJob `.exe` is only the win32 fallback. `LLAMA_N_GPU_LAYERS` overrides `eval.llama_n_gpu_layers` if set.

## Tree

```text
config.yaml          # Pins, corpora, llm.agents, TSR weights (no secrets)
.env / .env.example  # Secrets
CONTEXT.md           # Glossary
AGENTS.md            # Short agent operating notes
CODEBASE.md          # Module map for coding agents
src/rasa_skill_eval/ # Library: project, NVIDIA, improver, TSR, report filler
data/eval/scenarios/ # Rasano + personalization assertion YAML
data/skills/unslop/  # Unslop improver skill
corpus/              # Fetched examples (gitignored clones; pins/*.sha committed)
docs/REPORT.md       # Committed report template (placeholders only)
docs/ATTRIBUTION.md  # Corpus, prompt skill, and runtime license attribution
runs/heroes_eval_20260920_182120/  # Slim filled snapshot (REPORT, IMPROVER_DELTA, MANIFEST, plots, unique SKILL.md)
docs/adr/            # Short architecture decisions
tests/               # Pytest
```

## What is evaluated

- **Layer A:** Rasano and personalization projected skills — NVIDIA quality before/after writing-for-agents + unslop.
- **Layer B:** Live weighted/strict TSR and tokens/task on native vs reverse-merged trees, for each `llm.agents` entry. DeepEval is a secondary judge (`task_completion`, `answer_relevancy`, `tool_correctness`, `g_eval_tool_correctness`) plotted as `plots/deepeval_*.png`.
- Improver output is never written onto gitignored `corpus/`. Agent A/B uses copies under `runs/.../agents/`.

## Heroes submission

This directory is the wave-01-mantle project. Filled numbers: [runs/heroes_eval_20260920_182120/REPORT.md](runs/heroes_eval_20260920_182120/REPORT.md). Run manifest & reproducible boundary: [runs/heroes_eval_20260920_182120/MANIFEST.md](runs/heroes_eval_20260920_182120/MANIFEST.md). Corpus and license attribution: [docs/ATTRIBUTION.md](docs/ATTRIBUTION.md). Methodology: [docs/HEROES_EVAL_BRIEF.md](docs/HEROES_EVAL_BRIEF.md). Module detail: [CODEBASE.md](CODEBASE.md).
## Local process ownership

Evaluation cleanup signals only child handles started by the current Python
process. A matching external model server can be reused, but it is not adopted
or stopped. A wrong-model listener or an unowned peer-port conflict refuses a
local switch before downloads or startup. Stop that service through its owner,
or choose another configured port; the evaluator does not take it over.

A fresh `local_llm stop` invocation has no retained child ownership and refuses
an occupied unowned port. It does not discover arbitrary PIDs to kill them.
The same rule applies when switching to hosted actors and during final cleanup.

## Fresh corpus fetches and historical results

`fetch-corpus` clones the current repository HEAD and writes fetch receipts in
`corpus/pins/`; it does not check out the commits recorded by an earlier run.
A fresh fetch is therefore not an exact replay of the September inputs. The
saved report and manifest remain historical evidence. The default fetch
command does not implement exact historical replay.
