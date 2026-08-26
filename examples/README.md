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
mantle-voice-<domain>-skills
```

Examples: `mantle-voice-banking-skills`, `mantle-voice-telco-skills`.

The flagship travel agent is `mantle-voice-agent`, without a domain suffix. New examples should follow the domain-skills pattern unless there is a strong reason not to.

Each example is one directory with its own `README.md`, `pyproject.toml`, and (for Mantle voice agents) the usual Skills layout documented in that project’s `AGENTS.md`.

---

## Catalog

| Name | Persona | Domain | Path | Assessed on |
|---|---|---|---|---|
| Atlas voice travel | Atlas | Horizon Travel | [`mantle-voice-agent`](mantle-voice-agent) | 2026-08-13 |
| Rasano voice banking | Rasano | Retail banking | [`mantle-voice-banking-skills`](mantle-voice-banking-skills) | 2026-08-13 |
| Telano voice telecom | Telano | Telecom care | [`mantle-voice-telco-skills`](mantle-voice-telco-skills) | 2026-08-13 |
| Poly voice insurance | Poly | Insurance | [`mantle-voice-insurance-skills`](mantle-voice-insurance-skills) | 2026-08-13 |
| Schedora voice appointments | Schedora | Clinic booking | [`mantle-voice-appointment-skills`](mantle-voice-appointment-skills) | 2026-08-13 |
| Autono voice car purchase | Autono | Auto retail | [`mantle-voice-car-purchase-skills`](mantle-voice-car-purchase-skills) | 2026-08-13 |

When you add an example, append a row here in the same PR.

---

## How to add an example

1. Follow [CONTRIBUTING.md](../CONTRIBUTING.md) (one resource per PR, must run).
2. Start from [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md).
3. Add the catalog row above.
4. Area review: [MAINTAINERS.md](../MAINTAINERS.md).
