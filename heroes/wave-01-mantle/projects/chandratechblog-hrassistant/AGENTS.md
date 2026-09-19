# Rasa Mantle project — agent context

This directory is a **Rasa Mantle** agent (currently beta).
Mantle is Rasa's LLM-native engine: you describe behaviour in natural language
(`agent.yml`, skills) instead of hand-authoring intents, stories, and rules.

## Project layout

- `agent.yml` — the agent definition: an `agent:` block (`language`, `persona`)
  plus global HR support rules.
- `integrations.yml` — LLM provider config and enabled channels (REST, Inspector).
- `skills/<name>/skill.md` — one skill per directory: YAML frontmatter (`name`,
  `description`) plus natural-language instructions. This project includes
  `hr_concierge`, `hr_policies`, `hr_ticketing`, `hr_attendance`, and
  `hr_leave_management`, with JSON-backed demo tools where lookups or submissions
  are needed.
- `skills/<name>/tools.py` — optional Python tools a skill can call, defined with
  the `@tool` decorator from `rasa.mantle.tools`.
- `skills/<name>/memory.yml` — optional skill-scoped memory fields (e.g. the
  selected account id used to gate lookup tools).
- `.env` — secret values (license key, API keys). Never commit this file.

## Build loop

Run these from the project directory, with the project's virtualenv on PATH:

```
rasa train             # validate and build a model into models/
rasa inspect           # open the Inspector UI to chat with the agent
```

Re-run `rasa train` after editing `agent.yml`, `integrations.yml`, or any skill.

## Where skills guidance lives

Coding-agent skills for building Mantle projects are installed under
`.claude/skills/` (Claude Code) and `.cursor/skills/` (Cursor). Read them before
adding or changing skills.

## Ground rules

- Reference secrets only as `${ENV_VAR}` (e.g. `${OPENAI_API_KEY}`); never inline
  raw keys into YAML.
- Do **not** create CALM v1 files here — no `domain.yml`, no `config.yml`, no
  `data/` NLU files. Mantle (`mantle`) does not use them.
- Keep each skill focused on one job; add a new `skills/<name>/` directory rather
  than overloading an existing skill.

## Documentation

The full Mantle documentation is bundled locally at `.rasa/docs/mantle/`. It is the
single source of truth for syntax and behaviour — the installed skills teach the
common paths, this reference settles everything else.

### When to look it up

Read the page rather than guessing before you:

- write a `skill.md` frontmatter key you have not already seen in this project
- write a condition expression (`requires:`, `if:`, `complete_when:`, `next:`)
- write an `agent.yml`, `integrations.yml`, `memory.yml`, or `responses.yml` key
- add a file or folder to the project
- explain a `rasa train` error
- answer any question about how Mantle works — concepts, runtime behaviour, what a
  config key does, what the framework guarantees

Mantle is beta and post-dates your training data. What you recall about "Rasa" is
almost certainly **CALM v1**, a different engine: flows, slots, `domain.yml`,
intents, and stories do not exist in Mantle. Do not answer from memory. State the
`Source:` path of any page you relied on, and if you answer without reading a page,
say so explicitly.

### How to read it

**Never read `llms-full.txt` in full — it is ~250 KB (~65k tokens).** Use:

```bash
# 1. Page index, one line per page (small — safe to read whole)
cat .rasa/docs/mantle/llms.txt

# 2. Find which page documents a term
grep -n "requires_confirmation" .rasa/docs/mantle/llms-full.txt

# 3. Read one whole page — change only the quoted path
awk -v p="Source: /reference/skill-md" \
  '$0==p{f=1;print;next} f&&/^Source: /{exit} f' .rasa/docs/mantle/llms-full.txt

# 4. Map line numbers to pages, to resolve a grep hit to its page
grep -n "^Source: " .rasa/docs/mantle/llms-full.txt
```

Command 3 stops before the next page's `Source:` line, so its output belongs to one
page only — the final line may be the following page's `#` heading, which you can
ignore. Match the path exactly: `/skills` and `/mantle/skills` are different pages.
Keep the awk program in single quotes — in double quotes the shell expands `$0`
before awk sees it, and the command then returns nothing instead of failing.

Each Mantle skill lists the pages relevant to its own topic under **Further
reading** — take the `Source:` path from there and pass it to command 3.

### The mantle-docs skill

The **mantle-docs** skill carries the same commands plus the full page index, and
is the right entry point when you do not already know which page you need:

- a question about Mantle that no other skill covers
- you know the term but not the page — it routes term to page in one step
- this project has no `AGENTS.md` (skills installed into an existing project), so
  these instructions are not loaded

### When the bundle is missing

Re-run `rasa tools init docs mantle`. Failing that, the same pages are online at
https://rasa-2f7eb63d.mintlify.site — `/llms.txt` and `/llms-full.txt`. Do not
answer from memory instead.
