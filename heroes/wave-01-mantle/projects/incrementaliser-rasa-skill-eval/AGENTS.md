# Agent notes

- Run `uv run pytest` and `uv run ruff check src tests scripts` before claiming green.
- Do not edit `corpus/` by hand. Re-fetch with `uv run fetch-corpus`.
- Native Mantle `skill.md` is not SkillEvaluator input. Score projected copies only.
- Layer B trains from `runs/*/agents/<agent>/<model>/<arm>/` after reverse-merge. Never train on `runs/*/improved` projected folders.
- Glossary: [CONTEXT.md](CONTEXT.md). Module map: [CODEBASE.md](CODEBASE.md). Report template: [docs/REPORT.md](docs/REPORT.md) (numbers fill only under `runs/`).
