# Heroes evaluation brief

```text
Author:        Arash, Rasa Heroes
Wave:          wave-01-mantle
Verified with: rasa-pro 3.20.0.dev6 pin, Mantle, NVIDIA SkillEvaluator
Audience:      Rasa Heroes and Mantle maintainers
```

The narrative template is [REPORT.md](REPORT.md). Numbers appear only in filled run reports under `runs/`.

## Goal

1. Score Mantle example skills with NVIDIA SkillEvaluator after a **required format conversion**.
2. Improve projected copies with `writing-for-agents` + unslop.
3. Measure the effect on live Rasano and personalization as **weighted TSR**, strict TSR, and tokens/task across `llm.agents`.

NVIDIA is a coding-agent linter. It is not a Mantle runtime. Native `skill.md` is not SkillEvaluator input.

## Dual run

Native Mantle. Parse `skill.md`. Inventory `tool_constraints`, confirmation, `if:`, ordered blocks, project vs skill memory.

Projected Agent Skills. Kebab-case `SKILL.md`, extra YAML in `config/mantle.yml`, local tools in `scripts/`. Every NVIDIA command runs on this copy.

Reverse-merge. Description + body from improved `SKILL.md` back onto native `skill.md` for `rasa train`. Mantle keys stay. Agent copies rewrite `integrations.yml` and `endpoints.yml` to each `llm.agents` entry so train does not require `OPENAI_API_KEY`. Scenarios run over `rasa run --enable-api`.

## TSR

Each scenario-run scores applicable components, then

`TSR_weighted = sum(w_i s_i) / sum(w_i)`.

Defaults in `config.yaml`: skill started 0.20, tools 0.30, memory 0.20, confirmation 0.15, safety 0.15. Inapplicable components drop out of the denominator. Strict TSR is 1 only if every applicable component is 1.

## Reproduce

```powershell
uv run fetch-corpus
uv run eval-all
```
