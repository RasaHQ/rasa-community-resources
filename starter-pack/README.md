# Rasa Mantle starter pack

Everything here is distilled from the byte-verified projects in this catalog —
each rule below encodes a failure a real project in this repository actually
hit, not a guess about what might go wrong.

**Who this is for:** someone who has never built a Rasa Mantle agent and wants
to ship a good one fast, with tooling that catches the known traps before they
cost an afternoon.

## What's in the box

```
starter-pack/
├── CLAUDE.md                          # drop into your new repo root
├── .claude/
│   ├── skills/                        # Claude Code skills (auto-discovered)
│   │   ├── mantle-new-project/        # scaffold a working project
│   │   ├── mantle-agent-config/       # agent.yml without the silent traps
│   │   ├── mantle-skill-authoring/    # skill.md grammar that actually parses
│   │   ├── mantle-tools-and-memory/   # tool scope, memory scope, ToolResult
│   │   ├── mantle-llm-and-integrations/ # model groups, channels, credentials
│   │   └── mantle-upgrade-and-debug/  # version pins, rename, failure→cause map
│   └── agents/
│       ├── mantle-builder.md          # role: implements against the checklist
│       └── mantle-reviewer.md         # role: reviews bytes, runs the lint
├── scripts/
│   └── lint_mantle.py                 # standalone, zero-dependency project lint
└── hooks/
    ├── pre-commit                     # runs the lint on every commit
    └── install-hooks.sh               # one command to wire it up
```

## Ten-minute start

```bash
# 1. Copy the pack into your new project repo
cp -R starter-pack/CLAUDE.md starter-pack/.claude starter-pack/scripts starter-pack/hooks  my-agent/
cd my-agent && git init

# 2. Install the git hook (lint runs on every commit from now on)
./hooks/install-hooks.sh

# 3. Open Claude Code and say:
#      "use the mantle-new-project skill to scaffold a <your domain> agent"
#    The skill scaffolds every file with the correct 2026 shapes.

# 4. Gate it yourself any time:
python3 scripts/lint_mantle.py
```

## The one fact that breaks everything if you miss it

The Mantle engine (`rasa.mantle`) ships **only on the pre-release line**
`3.20.0.dev*`. The newest *stable* `rasa-pro` on PyPI contains **no engine
package at all** — pinning "latest stable" produces a project that cannot
import a single tool. Pin a `3.20.0.dev` release and set
`[tool.uv] prerelease = "allow"`. The lint checks this.

## What the lint catches ahead of time

Every check maps to a real, named failure (see `scripts/lint_mantle.py`
docstrings for the full story):

| Check | The failure it prevents |
| --- | --- |
| `agent-top-level-keys` | `rules:`/`name:`/`references:` nested under `agent:` parse fine and are **silently discarded** — an agent running without its guardrails, no warning anywhere. |
| `llm-model-group` | Inline `provider:`/`model:` under `llm:` — rejected since 3.20.0.dev6 with `'provider': Extra inputs are not permitted`, only at validate time. |
| `project-memory-writes` | `llm_settable: true` in root `memory.yml` — the engine rejects it outright; it belongs in skill-scoped memory. |
| `nested-if` | An indented `if:` in a skill body is instruction prose, not a condition. Your branch never branches. |
| `skill-prose` | Raw `session.x.y` in prose is **not substituted**; only `@memory.<ns>.<entry>` (exactly three parts) is. |
| `engine-version-pin` | Stable pin / missing `prerelease = "allow"` / Python floor below 3.11 — each fails with an error message that never names the actual cause. |
| `secret-hygiene` | A committed `.env`, an `sk-…` key or a JWT licence in tracked text. |
| `env-example` | A required credential your `.env.example` never mentions — undiscoverable until train breaks. |
| `retired-brand` | The retired pre-Mantle product name in a runnable command — the CLI already rejects it. (Not written out here; the lint that catches it scans this file too.) |

## Provenance

Assembled 2026-09-02 from `RasaHQ/rasa-community-resources` at rasa-pro
`3.20.0.dev6`: the catalog's `scripts/lint_repo.py` (every check there "encodes
a failure this repository has actually hit"), `docs/MIGRATING.md`, and the
shipped tutorials/examples/patterns. When the engine reaches a stable release,
re-check the version guidance here first — it is the piece most likely to age.
