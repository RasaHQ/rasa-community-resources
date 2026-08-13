# Patterns

Small, focused reference implementations of problems that recur when building and operating Rasa agents — tool design, evaluation harnesses, deployment shapes, observability, human handover, and similar.

This folder is **accepting contributions**. There are no patterns checked in yet.

---

## What belongs here

- One recurring problem, solved clearly, in a directory others can copy from
- A README with the standard metadata block and a short “when to use this” note
- Runnable or copy-pasteable code that stands alone without being a full product agent

## What does not belong here

| Instead put it in… | When… |
|---|---|
| [`examples/`](../examples/) | You are shipping a complete domain agent |
| [`tutorials/`](../tutorials/) | You need a multi-step teaching spine |
| [`snippets/`](../snippets/) | A few lines or a single file with no surrounding pattern |
| [`workshops/`](../workshops/) | Classroom timing, slides, and graded exercises |

---

## Naming

Prefer a short problem-oriented slug:

```text
<problem>-<approach>
```

Examples: `human-handoff-ticket`, `tool-constraints-progressive`, `eval-conversation-suite`.

---

## Catalog

| Name | Problem | Path | Assessed on |
|---|---|---|---|
| — | — | — | — |

_No patterns yet. Your PR can be the first row._

---

## How to add a pattern

1. Follow [CONTRIBUTING.md](../CONTRIBUTING.md).
2. Start from [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md).
3. Replace the empty catalog row with your entry.
4. Area review: [MAINTAINERS.md](../MAINTAINERS.md).
