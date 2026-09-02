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

Three examples name the **voice stack** rather than a domain — `mantle-voice-rime-skills`, `mantle-voice-speechmatics-skills` and `mantle-voice-routed-skills`. They share one banking agent on purpose, so the voice stack is the only thing that differs between them; naming them by domain would have made them look like duplicates of each other and of `mantle-voice-banking-skills`. Read them in that order: one vendor Rasa ships, one it does not, then a chain of both with a local model behind it.

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
| Vela voice banking on Rime | Vela | Retail banking / Rime TTS | [`mantle-voice-rime-skills`](mantle-voice-rime-skills) | 2026-08-26 |
| Vela voice banking on Speechmatics | Vela | Retail banking / custom ASR | [`mantle-voice-speechmatics-skills`](mantle-voice-speechmatics-skills) | 2026-08-26 |
| Vela voice banking, routed | Vela | Retail banking / vendor failover | [`mantle-voice-routed-skills`](mantle-voice-routed-skills) | 2026-09-02 |

When you add an example, append a row here in the same PR.

---

## How to add an example

1. Follow [CONTRIBUTING.md](../CONTRIBUTING.md) (one resource per PR, must run).
2. Start from [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md).
3. Add the catalog row above.
4. Area review: [MAINTAINERS.md](../MAINTAINERS.md).
