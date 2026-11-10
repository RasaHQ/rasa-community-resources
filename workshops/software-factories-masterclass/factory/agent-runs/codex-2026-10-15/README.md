# Nine recorded Codex runs on the Mantle factory

Agent: `codex-cli 0.162.1`, `codex exec --sandbox workspace-write --skip-git-repo-check`, run on October 15, 2026, on macOS, one attempt per task, three rounds (tasks A1, A2, A3). Engine: `rasa-pro 3.21.0.dev5`. The prompt for each: "Read tasks/<ID>.json and carry out the request. Follow AGENTS.md." Each ran in a folder made by `scratch.py`, was collected by `collect.py` and judged by `factory.py` with nothing edited by hand.

Per run: `decision.json` (the factory's record), `meta.json` (agent, seconds, agent exit status, human interventions: 0), `final-message.txt` (the agent's own account, a claim), `change.patch` and `review.json` (the collected change).

Not recorded: cost. The driver scripts that ran them are in `../drivers/`. Read them with `uv run python measure.py report agent-runs/codex-2026-10-15`.

The Claude Code runs are in `../claude-code-2026-10-15/`.
