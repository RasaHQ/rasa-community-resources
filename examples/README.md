# Examples

Complete, clone-and-run Rasa agents. Prefer an example when you want a finished project to adapt, not a guided chapter-by-chapter build (those live under [`tutorials/`](../tutorials/)).

---

## What belongs here

- A **full agent** with its own README, dependencies, and quick-start path
- Seeded demo data when the domain needs it
- Optional `tutorial/` snippets if the example also supports a live session — the primary deliverable is still the finished agent

## What does not belong here

| Instead put it in… | When… |
|---|---|
| [`tutorials/`](../tutorials/) | The main product is the walkthrough |
| [`patterns/`](../patterns/) | A small focused reference, not a full agent |
| [`snippets/`](../snippets/) | A fragment too small to run alone |
| [`workshops/`](../workshops/) | Slide decks and timed exercises |

---

## Naming

Prefer:

```text
maestro-voice-<domain>-skills
```

Examples: `maestro-voice-banking-skills`, `maestro-voice-telco-skills`.

The flagship travel agent uses `maestro-voice-agent` for historical continuity with the hosted community tutorial. New examples should follow the domain-skills pattern unless there is a strong reason not to.

Each example is one directory with its own `README.md`, `pyproject.toml`, and (for Maestro voice agents) the usual Skills layout documented in that project’s `AGENTS.md`.

---

## Catalog

| Name | Persona | Domain | Path | Assessed on |
|---|---|---|---|---|
| Atlas voice travel | Atlas | Horizon Travel | [`maestro-voice-agent`](maestro-voice-agent) | 2026-08-13 |
| Rasano voice banking | Rasano | Retail banking | [`maestro-voice-banking-skills`](maestro-voice-banking-skills) | 2026-08-13 |
| Telano voice telecom | Telano | Telecom care | [`maestro-voice-telco-skills`](maestro-voice-telco-skills) | 2026-08-13 |
| Poly voice insurance | Poly | Insurance | [`maestro-voice-insurance-skills`](maestro-voice-insurance-skills) | 2026-08-13 |
| Schedora voice appointments | Schedora | Clinic booking | [`maestro-voice-appointment-skills`](maestro-voice-appointment-skills) | 2026-08-13 |
| Autono voice car purchase | Autono | Auto retail | [`maestro-voice-car-purchase-skills`](maestro-voice-car-purchase-skills) | 2026-08-13 |

When you add an example, append a row here in the same PR.

---

## How to add an example

1. Follow [CONTRIBUTING.md](../CONTRIBUTING.md) (one resource per PR, must run).
2. Start from [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md).
3. Add the catalog row above.
4. Area review: [MAINTAINERS.md](../MAINTAINERS.md).
