---
name: maestro-configuring-agent
description: >
  Configures the Maestro project config files: agent.yml (identity, persona, rules,
  prompt tuning, session settings), integrations.yml (LLM provider, channels
  including voice ASR/TTS, model groups, Langfuse tracing), memory.yml (schema, cross-skill
  visibility), and responses.yml (verbatim templates). Use when setting up or
  changing any of these files.
license: Apache-2.0
engine: maestro
rasa_version: ">=3.18"
metadata:
  author: rasa
  version: "0.1.5"
  docs-url: https://rasa-2f7eb63d.mintlify.site
---

# Configuring a Maestro agent

Project layout:

```
my-agent/
├── agent.yml              # Required. Identity, persona, rules, prompt tuning
├── integrations.yml       # Required. LLM provider, channels, optional Langfuse tracing
├── memory.yml             # Optional. Project-wide shared memory
├── responses.yml          # Optional. Project-wide responses, overrides built-in wording
├── references/            # Optional. Agent-wide knowledge, every **/*.md is indexed
├── tools/                 # Optional. Shared tools, declared with import_tools
└── skills/
    └── <skill>/           # The folder name is the skill id
        ├── skill.md       # Required. The only required file in a skill
        ├── memory.yml     # Optional. Skill-scoped memory schema
        ├── responses.yml  # Optional. Verbatim wording
        ├── tools.py       # Optional. Skill-local tools, auto-discovered
        ├── tools/         # Optional. Or a folder of them, also auto-discovered
        └── references/    # Optional. Indexed into the same project-wide index
```

Start minimal: `agent.yml` with an `agent:` block carrying `persona`, plus
`integrations.yml` with an `llm:` block and a `channels:` block, is a complete
config. Add sections only when a feature needs them. The engine is selected by
project layout, so there is no version key to set.

## agent.yml — identity and persona

```yaml agent.yml
agent:
  id: telco-support
  language: en
  persona: |
    You are Telco support, a friendly and concise customer service agent.

rules:
- Help with billing and plan questions only.
- >
  Look up the account with the account-lookup tool before quoting a balance:
  never guess a number.

prompts:
  text_rules: |
    Plain sentences only. No markdown or bullet lists.

session_config:
  session_expiration_time: 60
```

The file has **two levels**, and mixing them up is the most common mistake:

- Inside `agent:`: `id`, `language`, `persona`. An `agent:` block is required, and
  `persona` must be a non-empty string inside it. A file with no `agent:` block
  fails to load with `config.agent.missing_section`; a missing persona fails with
  `config.agent.missing_persona`.
- **Top-level siblings** of `agent:`: `rules`, `prompts`, `references`,
  `conversation`, `session_config`. Nesting these inside `agent:` means they are
  never read, and unknown keys are ignored rather than rejected, so the mistake is
  silent.

Notes:

- `persona` sets global tone and identity.
- `rules` are global do/don't guidance rendered into every prompt (scope limits,
  tone guards, ordering constraints). Quote any rule containing a colon followed by
  a space, or write it as a `>` folded scalar; an unquoted colon parses as a YAML
  mapping and breaks the load.
- `prompts` overrides individual sections of the system prompt: `text_rules`,
  `voice_rules`, `ack_rule`, `ack_reminder`, `ack_enabled`, `ack_examples`,
  `routing_no_active_skill`. Leave one unset to keep its built-in default.
- `id` is generated and written back into the file when absent.

## integrations.yml — providers and infrastructure

Holds the LLM provider, the input channels customers reach the agent through and optional Langfuse tracing.
Never put a literal key in this file. Use `api_key_env` in the `llm:` block, which
names an environment variable and works for every provider. `${ENV_VAR}` expansion
happens in the `channels:` block, which is read with environment variables
expanded; `llm:` and `model_groups:` are not.

```yaml integrations.yml
llm:
  provider: openai
  model: gpt-5.1
  api_base: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY    # env var NAME, not ${...}; value read at load time

channels:
  rest: { enabled: true }        # REST input (evaluation / HTTP channel)
  inspector: { enabled: true }   # required for `rasa inspect`

# Langfuse tracing (optional). Install rasa-pro[monitoring], set
# LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY, then uncomment. Keys use ${VAR}
# syntax; they resolve when Langfuse configures at startup, not at YAML load.
# tracing:
#   type: langfuse
#   public_key: ${LANGFUSE_PUBLIC_KEY}
#   private_key: ${LANGFUSE_SECRET_KEY}
#   host: https://cloud.langfuse.com
```

`llm` is the single model that drives the agent: one flat block with `provider` at
its top level, plus `model` (or `deployment` for Azure OpenAI). It is never a
`model_groups` reference. Providers `openai`, `azure`, and `self-hosted` have
dedicated clients; any other value is passed to LiteLLM, so `anthropic` or `gemini`
work by naming the provider and its model. `tracing` is optional and lives here

`channels` declares the channels customers reach the agent through. `rest` and
`inspector` are the minimum for local work: `rest` is what the evaluation runner
talks to, and `inspector` is required for `rasa inspect`.

### Voice channels

Speech recognition and synthesis are configured **inside the voice channel entry**,
under `asr:` and `tts:`. Each takes a `name:` selecting the engine plus that
engine's own settings:

```yaml integrations.yml
channels:
  browser_audio:
    enabled: true
    server_url: localhost:5005
    asr:
      name: deepgram
      language_map:
        en-US:
          language: en
          model: flux-general-en
      eot_threshold: 0.8
    tts:
      name: deepgram
      language_map:
        en-US:
          model: aura-2-asteria-en
```

Built-in ASR engines: `deepgram`, `azure`. Built-in TTS engines: `deepgram`,
`azure`, `cartesia`, `rime`. The same `asr:` / `tts:` shape applies to every voice
channel, including `jambonz`, `audiocodes`, and `twilio_media_streams`; what
differs is the telephony connection.

### model_groups

Optional, and used today by the references embedder. Declare a group and name it
from `agent.yml`:

```yaml integrations.yml
model_groups:
  - id: reference_embeddings
    models:
      - provider: openai
        model: text-embedding-3-large
```

```yaml agent.yml
references:
  embeddings: reference_embeddings
```

`model_groups` is read from the packaged model rather than the live project, so
changing the embedding model needs a retrain.

## Knowledge (RAG)

There is no config for this. Put markdown files in a `references/` folder, at the
agent root or inside a skill, and `rasa train` indexes every `**/*.md` into the
model. The agent then gets the built-in `search_knowledge` tool automatically.

Both locations feed one index, and a search covers all of it whatever skill is
active, so write each document to stand on its own.

## memory.yml — state schema

A skill's own state lives in `skills/<skill>/memory.yml`; state shared across skills
lives in a project-level `memory.yml` at the agent root (it resolves to the
`project.` namespace). Declare every key a tool writes — `rasa train` rejects
an undeclared `context.memory.set()` with `undeclared_memory_write`.

```yaml skills/card_replace/memory.yml
schema:
  public:                      # readable by every other skill, at any time
    replacement_reason:
      type: categorical        # enum_values constrains what the LLM may record
      enum_values: [lost, stolen, damaged, not_received]
      description: Why the card is being replaced.
    selected_card_id:
      type: text
      description: Account id of the chosen card.
  private:                     # internal to this skill
    eligibility_checked:
      type: bool
      description: Whether account eligibility was verified.
```

Types: `text`, `bool`, `int`, `float`, `list`, `json`, `categorical` (with
`enum_values`), and `any`. Give each a `description`: it is what the LLM sees when
deciding whether to record a value.

Add `llm_settable: true` to let the LLM write an entry itself. Leave it off for
engine-derived values such as eligibility results or computed flags, so the model
can neither invent nor revise them. A value owned by a `collect:` step is settable
either way, since the engine asked the user for it directly.

A project-level `memory.yml` uses the same `type`/`description` shape but as a flat
map of top-level keys, with no `schema:`/`public:`/`private:` wrapper.

Design rule: `public` is the skill's API. Another skill gating on
`session.project.authenticated` depends only on that key, not on the auth skill
itself — keep public entries few and stable.

How you **reference** a declared entry depends on where you write it:
`session.*` in conditions and structured YAML (`requires:`, `if:`, execute
`parameters:`); `@memory.*` in instruction prose; `{session.*}` in
`responses.yml`; bare or qualified keys in `context.memory.get(...)` inside
`tools.py`. See the fully-qualified names table in the memory.yml reference.

## responses.yml — verbatim text

Lives inside a skill folder, or at the agent root to apply project-wide. The
framework delivers the text directly and the LLM never rewrites it.
`{session.<skill_id>.<entry>}` interpolates at delivery time, as does the bare
`{entry}` form for the skill's own values.

Every `responses.yml` merges into one registry keyed by name, so response names are
global. Prefix them with the skill they belong to. Declaring a built-in name such as
`utter_greet` in the project-root file replaces the bundled one.

```yaml skills/card_replace/responses.yml
responses:
  utter_recording_notice:
    - text: >-
        This interaction may be recorded for quality assurance
        and training purposes.
  utter_replacement_failed:
    - text: >-
        We were unable to process your replacement. A support ticket has
        been created. Reference: {session.card_replace.ticket_id}.
```

Use verbatim responses for wording that must be exact (legal, compliance,
brand-mandated). Four things reference a response by name:

- a frontmatter `utter:` trigger, with `on: activate` or a `when:` condition
- `on_success:` / `on_failure:` on a `tool_constraints` entry
- `utter_for_confirmation` / `utter_on_user_denial` under `requires_confirmation:`
- an ordered-block `action:` step, or `utterance:` on a `collect:` step

`rasa train` validates every one of those names. Everything else stays prose so the
agent sounds natural.

## Don't

- Don't put secrets literally in any of these files. Use `api_key_env` in `llm:`
  and `${ENV_VAR}` in `channels:`.
- Don't nest `rules`, `prompts`, `references`, `conversation`, or `session_config`
  inside the `agent:` block. They are top-level siblings, and nesting them is
  ignored silently.
- Don't put skill behavior in `persona` or global config; behavior belongs in the
  owning skill's `skill.md`.
- Don't create `domain.yml`, `config.yml`, `credentials.yml`, or an
  `endpoints.yml` just for Langfuse — those are CALM files. LLM, channel, and
  Langfuse tracing config live in `integrations.yml`.
- Do declare every memory key a tool writes — undeclared `context.memory.set()`
  writes fail `rasa train` (`undeclared_memory_write`).
- If `rasa train` rejects a section, read the reference page for that file below
  before assuming a bug. Its error names the file and key at fault.

## Further reading

Full Maestro documentation: https://rasa-2f7eb63d.mintlify.site

Fetch `https://rasa-2f7eb63d.mintlify.site/llms.txt` for the page index, or
`https://rasa-2f7eb63d.mintlify.site/llms-full.txt` for every page in one file.
Read the specific page when this file is not enough; do not guess syntax.

Most relevant here:

- [Project structure](https://rasa-2f7eb63d.mintlify.site/reference/project-structure): every file and folder an agent recognises, and which are required
- [agent.yml reference](https://rasa-2f7eb63d.mintlify.site/reference/agent-yml): every key, and which are top-level rather than nested
- [integrations.yml reference](https://rasa-2f7eb63d.mintlify.site/reference/integrations-yml): LLM providers, channels, voice ASR/TTS, model groups
- [memory.yml reference](https://rasa-2f7eb63d.mintlify.site/reference/memory-yml): skill schema vs project memory, types, access control
- [responses.yml reference](https://rasa-2f7eb63d.mintlify.site/reference/responses-yml): templates, interpolation, and the four ways a response fires
