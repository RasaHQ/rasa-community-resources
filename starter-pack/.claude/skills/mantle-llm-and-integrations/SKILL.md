---
name: mantle-llm-and-integrations
description: >
  Configure integrations.yml — LLM model groups, providers, channels, and
  credentials — for a Rasa Mantle project. Use when changing the LLM/provider,
  adding channels, wiring API keys, or when validate fails with "'provider':
  Extra inputs are not permitted" or "'model_group': Field required".
---

# integrations.yml — model groups, channels, credentials

## The breaking change everyone hits

Since rasa-pro **3.20.0.dev6**, the orchestrator LLM config is
`extra="forbid"` with a **required `model_group`**. The old inline form —
`provider:`/`model:`/`api_key:` directly under `llm:` — fails validate with:

```
'provider': Extra inputs are not permitted
```

and a missing reference fails with `'model_group': Field required`. The
inline form is easy to reintroduce by copying any pre-dev6 example from a
blog or older repo — assume every example you find online has this wrong.

## Correct shape

```yaml
llm:
  model_group: orchestrator

model_groups:
  - id: orchestrator
    models:
      - provider: openai
        model: gpt-4.1-mini
        api_key: ${OPENAI_API_KEY}
        temperature: 0.0

channels:
  rest:
    enabled: true
  inspector:
    enabled: true
```

- The `id` under `model_groups:` must match the `model_group:` reference.
- `temperature: 0.0` for orchestration — routing wants determinism.
- Alternative providers slot in at the group level (e.g.
  `provider: gemini`, `model: gemini-2.0-flash`,
  `api_key: ${GEMINI_API_KEY}`) — the `llm:` reference never changes.

## Credentials — the three-layer resolution

Keys resolve **shell env → project `.env` → repo-root `.env`**, first hit
wins. Consequences:

1. Every `${VAR}` used anywhere in yml MUST appear in `.env.example` with an
   empty value and a comment saying where to get it. A key the example never
   mentions is one a new user cannot discover — the failure surfaces later as
   an unexpanded `${GEMINI_API_KEY}` that looks like a broken project.
2. Non-default keys (anything beyond `RASA_LICENSE`/`OPENAI_API_KEY`) also go
   in `pyproject.toml`:

   ```toml
   [tool.rasa-catalog]
   required-secrets = ["GEMINI_API_KEY"]
   ```

3. `.env` is gitignored, always. Only `.env.example` is committed. Never put
   a real value in any committed file — the lint scans for `sk-…` keys and
   JWT-shaped licences.

## Voice provider keys

Voice vendors are optional-by-design done right: name every key in
`.env.example` but make the runtime skip providers whose credentials are
absent, and say so ("the router skips providers it has no credentials for").
An agent that hard-fails on a missing optional key punishes the beginner.

## Verify

`python3 scripts/lint_mantle.py --check llm-model-group --check env-example
--check secret-hygiene`, then `make validate` with real credentials.
