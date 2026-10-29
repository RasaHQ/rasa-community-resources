# Corpus and License Attribution

This document records the authorship, provenance, and license terms for this evaluation harness and every external corpus, prompt skill, or runtime tool it references. External works are governed by their own licenses and are not relicensed by this project.

## 1. Evaluation harness (`incrementaliser-rasa-skill-eval`)

- **Author:** Arash Ashrafzadeh (`@incrementaliser`)
- **License:** [Apache License 2.0](https://github.com/RasaHQ/rasa-community-resources/blob/main/LICENSE) (the root catalog license of `RasaHQ/rasa-community-resources`).
- **Scope:** All harness source code under `src/rasa_skill_eval/`, scripts under `scripts/`, unit tests and synthetic test fixtures under `tests/`, scenario definitions under `data/eval/scenarios/`, the local `data/skills/unslop/SKILL.md` prompt, the smoke Mantle project at the project root (`agent.yml`, `skills/check_status/`), and the evaluation report and figures under `runs/heroes_eval_20260920_182120/`.

## 2. Evaluated Mantle corpora (`rasano` and `personalization`)

- **Source repository:** [`RasaHQ/rasa-community-resources`](https://github.com/RasaHQ/rasa-community-resources)
  - `rasano`: `examples/mantle-voice-banking-skills`
  - `personalization`: `patterns/session-start-personalization`
- **Pinned commit:** `5070107f73d4048e86f876f1f42878e2244b2bb5` (recorded in [`corpus/pins/rasano.sha`](../corpus/pins/rasano.sha) and [`corpus/pins/personalization.sha`](../corpus/pins/personalization.sha)).
- **License:** Apache License 2.0 (`RasaHQ/rasa-community-resources`).
- **Distribution in this tree:** The upstream example trees are **not vendored** into git. They are fetched on demand into gitignored `corpus/rasano/` and `corpus/personalization/` by running `uv run fetch-corpus`. The 10 `runs/heroes_eval_20260920_182120/improved/<agent>/<skill>/SKILL.md` files are derivative Agent Skills prompt rewrites generated during the `2026-09-20` evaluation run from those Apache-2.0 skills.

## 3. Improver prompt skills (`writing-for-agents` and `unslop`)

- **`writing-for-agents`**
  - **Author:** Matt Pocock
  - **Source repository:** [`mattpocock/skills`](https://github.com/mattpocock/skills) (`writing-for-agents`)
  - **Pinned commit:** `c55ee46073ed923f86ce59a5eb3b6d895095d1b7` (recorded in [`corpus/pins/writing_for_agents.sha`](../corpus/pins/writing_for_agents.sha)).
  - **License:** MIT License (upstream repository license).
  - **Distribution in this tree:** Fetched on demand into gitignored `corpus/writing-for-agents/` via `uv run fetch-corpus`; **not copied** into this repository. (The file `tests/fixtures/coding_skill/writing-for-agents/SKILL.md` is a minimal 13-line synthetic stub written for offline unit testing.)
- **`unslop`**
  - **Location:** [`data/skills/unslop/SKILL.md`](../data/skills/unslop/SKILL.md)
  - **Author:** Arash Ashrafzadeh
  - **License:** Apache License 2.0 (declared in frontmatter).

## 4. Runtime engines and external evaluation tools

- **Rasa Pro (`rasa-pro==3.20.0.dev6`)**
  - **Provider:** Rasa Technologies GmbH
  - **License:** Proprietary Rasa Pro / Rasa Developer Edition license terms (requires `RASA_LICENSE` at runtime; not covered by Apache-2.0).
- **NVIDIA SkillEvaluator**
  - **Provider:** NVIDIA Corporation ([`NVIDIA/SkillEvaluator`](https://github.com/NVIDIA/SkillEvaluator))
  - **Usage:** Installed separately as an external CLI tool (`uv tool install --python 3.13 "skillevaluator[all] @ git+https://github.com/NVIDIA/SkillEvaluator.git"`). Not bundled or redistributed in this repository.
  - **Verification note:** All Layer A and Layer B evaluation numbers in `runs/heroes_eval_20260920_182120/` are the author's `2026-09-20` evaluation run, not an independent maintainer re-verification.
