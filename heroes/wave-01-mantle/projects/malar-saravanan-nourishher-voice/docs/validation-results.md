# Validation results (frozen snapshot)

Recorded for PR review. Pin: **`rasa-pro 3.20.0.dev6`** (`pyproject.toml`, `uv.lock`,
README `Verified with:`). Re-run after rebasing or changing dependencies.

## Environment

| Item | Value |
|------|--------|
| Date | 2026-10-21 |
| OS | Windows 11 |
| Python | 3.13.x via `uv` |
| Branch | `heroes/nourishher-voice` (post review edits) |

## Catalog lint (repository root)

```bash
uv run --python 3.13 python scripts/lint_repo.py \
  --check snapshot-pin --check index-rows --check resource-metadata \
  --check env-example --check secret-hygiene --check heroes-layout \
  --check fictional-data
```

**Result:** all 7 checks passed; no findings under `heroes/`.

## Project gates (project directory)

| Command | Result | What it exercises |
|---------|--------|------------------|
| `uv run python scripts/validate_project.py` (`make validate`) | **Pass** | Skills, memory, tool constraints |
| `uv run python -m unittest discover -s tests -v` (`make test`) | **9/9 pass** | File store + tools; **no LLM, no network** |
| `uv run python scripts/verify_setup.py` (`make verify`) | **Pass** (with local `.env`) | Keys present; **connectivity probes** to OpenAI, Groq, Gemini, Deepgram, USDA |
| `uv run rasa test e2e tests/e2e_test_cases.yml` (`make e2e`) | **4/4 pass** (prior run on pin) | Live orchestrator; greeting, meal log routing, `nutrition_qna` routing, safety escalation wording |

## Provider / voice coverage (explicit)

| Capability | Tested in automation? | Notes |
|------------|----------------------|--------|
| OpenAI orchestrator (primary) | **Yes** — `make e2e`, `make verify` connectivity | Required for e2e harness |
| Groq fallback | **Connectivity only** (`make verify`) | Not load-tested; fallback path not exercised in e2e |
| Gemini embeddings / rephraser | **Connectivity only** (`make verify`) | RAG paths not in e2e fixtures |
| Deepgram ASR/TTS (Inspector voice) | **Connectivity only** (`make verify`) | **Not** exercised by `make test` or `make e2e` (text-driven harness) |
| USDA FoodData Central | **Yes** — `make verify` + live tool use in e2e nutrition case | e2e asserts routing to `nutrition_qna`, not reply text |
| Browser UI (`ui/index.html`) | **Not automated** | Manual with `make api` + `make ui` |
| Condition-skill routing / levothyroxine reminder | **Not automated** | Documented manual checks in `tests/e2e_test_cases.yml`, `docs/mantle-features.md` |

## Rebase note

Maintainers indicated **no merge conflict** with `main` at review time; rebase onto
current `upstream/main` before merge if the base branch moves.
