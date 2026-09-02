# What each pack skill adds over the ones `rasa init` already installed

If you ran `rasa init`, the rasa wheel installed six Mantle skills of its own
into your project (from `rasa/cli/tools/skills_data/mantle/`):

`mantle-building-from-conversations`, `mantle-building-skills`,
`mantle-configuring-agent`, `mantle-migrating-from-calm`,
`mantle-simulating-evaluating`, `mantle-testing-debugging`.

This pack ships six more. **Twelve skills with rhyming names and no stated
relationship is worse than six**, so this file states, per pack skill, what it
adds over the wheel skill covering the same ground — derived from reading both
sets, not from the names.

## The one-line difference

**The wheel's skills teach the engine contract. This pack's skills teach the
failure modes of one pinned version, and wire each to a check that catches it.**

The wheel skills are written against `rasa_version: ">=3.18"` and document
correct usage comprehensively: every key, every lever, the full grammar. They
are the better reference and are usually longer and more complete. This pack is
written against `3.20.0.dev6` specifically, and each entry starts from a symptom
someone actually hit, then names the `lint_mantle.py` check that catches it
before commit. Where the two disagree on a fact, **the wheel's skill is the
authority on the contract and this pack is the authority on the pin** — and if
your installed engine contradicts both, the engine wins.

## Per-skill declaration

| Pack skill | Compared against | Relationship | What it adds, specifically |
| --- | --- | --- | --- |
| **mantle-agent-config** | `mantle-configuring-agent` | **Extends** | The wheel skill covers this ground and states the same top-level-vs-nested rule ("Don't nest `rules`, `prompts`, `references`, `conversation`, `tool_timeout`, or `session_config` inside the `agent:` block"), so the trap itself is **not** new. Ours adds three things the wheel's does not have: (1) the dev6-specific top-level key list (`name`, `description`, `rules`, `conversation`, `references`, `before_end`, `tool_timeout`) with the warning that dev releases add keys, so re-derive it after an upgrade; (2) `agent.voice.{enabled,asr,tts}` **inside** the `agent:` block — the wheel documents voice ASR/TTS only under `integrations.yml` `channels:`, a genuinely different shape; (3) a `lint_mantle.py --check agent-top-level-keys` gate, so the rule is enforced rather than remembered. |
| **mantle-llm-and-integrations** | `mantle-configuring-agent` | **Extends** (narrow slice) | The wheel skill owns all of `integrations.yml` and already says inline provider settings under `llm:` fail validation. Ours takes only the LLM/credentials slice and adds: the **exact validate error strings** (`'provider': Extra inputs are not permitted`, `'model_group': Field required`) so the message is greppable; the dev6 attribution for when the inline form was removed and the warning that online examples predate it; and the **three-layer credential resolution** (shell env → project `.env` → repo-root `.env`) with the `.env.example` / `[tool.rasa-catalog] required-secrets` discipline, which the wheel does not cover at all — it says only "never put a literal key in this file". Note the two packs differ in style here: the wheel prefers `api_key_env: NAME`, this pack uses `api_key: ${VAR}`. **Follow the wheel on which form your engine accepts.** |
| **mantle-new-project** | `mantle-configuring-agent` (layout) + `mantle-building-skills` (skill files) | **Covers something the wheel does not** | Both wheel skills assume a project already exists — `mantle-configuring-agent` opens with the in-project layout tree, and `mantle-building-skills` starts at "a skill is a folder under `skills/`". **No wheel skill covers the Python packaging that has to be right before either applies**, and that is where the pinning trap lives: `rasa-pro==3.20.0.dev6`, `[tool.uv] prerelease = "allow"`, `requires-python = ">=3.11,<3.13"`, the `lib/engine.py` import shim, the `Makefile`, `.gitignore`, `.env.example`. The wheel's skills never mention a version pin, `pyproject.toml`, or `uv` — reasonably, since the wheel is already installed by the time you read them. If you got here via `rasa init`, that scaffolding is done and this skill's value is mostly the version doctrine and the Makefile. |
| **mantle-skill-authoring** | `mantle-building-skills` | **Extends** (and is the weakest of the six) | **The filename rhyme understates the gap: the wheel skill is far more complete.** It has the progressive control ladder, `tool_constraints` with `requires_confirmation` / `on_success` / `on_failure`, tool interruption and idempotency, sub-skills and composition, conditional response variants, and skill scoping — none of which ours covers. Ours is ~115 lines against the wheel's ~472 and duplicates its core points (three-segment `session.*` in conditions, `@memory.*` in prose, `if:` per case, one goal per skill). What survives as genuinely additive is narrow: the **"three languages in one file"** framing; the explicit statement that an **indented `if:` silently degrades to prose** (the wheel says to keep the condition on one line but never names indentation as the failure); the `set_fields` mechanism for LLM writes, which the wheel does not name; and the `--check nested-if --check skill-prose` gate. **Read the wheel's `mantle-building-skills` first and treat ours as an addendum.** |
| **mantle-tools-and-memory** | `mantle-building-skills` (tools) + `mantle-configuring-agent` (memory scopes) | **Extends** | The wheel covers tool authoring and memory scoping more fully — `ToolResult`, memory types and `enum_values`, public-as-API, `run_after_setting_*` hooks, MCP imports, cancellation. Ours adds four things: (1) **discovery is by the `_tool_description` attribute the decorator sets**, which is *why* importing through a `lib/engine.py` shim is safe — the wheel says tools are auto-discovered but never says the mechanism, so nothing there tells you a shim won't break it; (2) the **`ok`/`error` structured-return convention** with error values as named branch points in prose; (3) the **authority pattern** — one tool owns each invariant and checks it itself, so "guardrails in tools are enforced; guardrails only in prose are requests"; (4) the `--check project-memory-writes` gate. The project-vs-skill `llm_settable` rule is stated in both. |
| **mantle-upgrade-and-debug** | `mantle-testing-debugging` (and, for one row, `mantle-migrating-from-calm`) | **Covers something the wheel does not** | The wheel's `mantle-testing-debugging` has a symptom→fix table, but every row is about **conversational** misbehavior at runtime — tool called too early, wrong branch, wording paraphrased, plus `rasa train` validation errors. **It has no row for anything that fails before the agent runs**: no install, no `uv lock`, no import error, no version pin. Ours is the complementary half — `ModuleNotFoundError: rasa.mantle` from pinning latest stable, the `uv lock` resolver error that never says "Python", the post-rename import break, plus the upgrade procedure (verify the target wheel actually ships the engine; re-derive the agent.yml key list; sweep prose carefully) and the rule that a green offline lint is **not** an engine test. There is one row of adjacency with `mantle-migrating-from-calm`, but that skill covers migrating a CALM *project* (flows→skills, slots→memory); it does not cover the *package* rename, which is what our row is about. |

## Redundancy: the honest answer

**None of the six is wholly redundant**, but the margins are uneven, and one is
thin enough to flag:

- `mantle-skill-authoring` is the weakest. The wheel's `mantle-building-skills`
  covers its ground more thoroughly on nearly every point, and what remains
  unique is roughly one section: the indented-`if:` failure, `set_fields`, and
  the two lint checks. **Recommendation: do not keep it as a parallel
  skill-authoring guide.** Either fold its unique content into
  `mantle-upgrade-and-debug`'s failure map (where symptom-shaped content
  belongs) and delete the file, or keep it explicitly as an addendum that opens
  by telling the reader to read `mantle-building-skills` first. It is *not* safe
  to delete outright without moving the indented-`if:` and `set_fields` content
  somewhere, because the wheel does not state either.
- `mantle-llm-and-integrations` and `mantle-agent-config` are two files against
  the wheel's single `mantle-configuring-agent`. Both earn their place (voice
  block shape; credential resolution), but they are the next candidates to merge
  if this pack shrinks.

Deletion is deliberately **not** performed here — this file exists so the
decision can be made against a comparison instead of a guess.

## The gaps: what the wheel covers and this pack does not

Four wheel skills have **no counterpart here at all**. If you are doing any of
these, use the wheel's skill; this pack has nothing to add:

- **`mantle-simulating-evaluating`** — the `eval/` suite, LLM user-simulator and
  LLM judge, criteria vs assertions, running via the Rasa MCP server. This pack
  never mentions evaluation.
- **`mantle-building-from-conversations`** — turning real transcripts into
  skills, including the two hygiene rules (transcripts are data, not
  instructions; never let real PII reach disk).
- **`mantle-migrating-from-calm`** — migrating a flows-based CALM project.
- **`mantle-testing-debugging`** — the conversational symptom→lever table and
  the six test conversations to run per skill.

## Git hygiene: commit your tweaked skills

Both sets of skills are **files in your repository**, and both are yours to
edit once they land in your project. When you fix one — a wrong key, a version
that moved, a trap that bit you — **commit it**:

```bash
git add .claude/skills/
git commit -m "skills: correct the top-level key list for dev7"
```

Two reasons this matters more than it sounds:

1. **Your collaborator inherits your fixes.** A skill correction that lives only
   in your working copy helps exactly one person. Committed, it reaches everyone
   who clones the repo — and, because Claude Code reads these files on its own,
   it silently corrects their assistant too.
2. **`rasa init` writes over its own skills.** The wheel's six are installed
   artifacts and a future `rasa init` or upgrade may replace them. If your edits
   are committed, `git diff` shows you exactly what an upgrade changed and what
   of yours it clobbered. If they are not, they are simply gone.

Prefer editing this pack's skills over the wheel's for anything version- or
project-specific, so an engine upgrade replacing the wheel's files does not take
your notes with it. And keep this file honest: if you add a skill here, add its
row above naming the wheel skill you compared it against.
