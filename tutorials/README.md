# Tutorials

Step-by-step walkthroughs with runnable code. Prefer a tutorial when the primary deliverable is the learning path (chapters, paste-ready snippets, hosted companion pages), not only a finished agent to fork.

---

## What belongs here

- A self-contained tree learners can check out and follow
- Clear chapter or step structure (`tutorial/snippets/`, `TUTORIAL.md`, and/or a link to a hosted guide on [rasa.community](https://rasa.community/))
- Honest time estimates in the resource README metadata

## What does not belong here

| Instead put it in… | When… |
|---|---|
| [`examples/`](../examples/) | The main product is a finished clone-and-run agent |
| [`patterns/`](../patterns/) | A small reference without a teaching spine |
| [`workshops/`](../workshops/) | Timed classroom packs with slides and solutions |
| [`snippets/`](../snippets/) | A fragment without a walkthrough |

---

## Naming

Prefer a descriptive slug:

```text
rasa-<topic>-tutorial
```

Example: `rasa-voice-agent-tutorial`.

If a tutorial is the companion to an example in `examples/`, say so in both READMEs so readers know which tree to start from. For Atlas travel, the recommended start is [`examples/mantle-voice-agent`](../examples/mantle-voice-agent) plus the [hosted voice tutorial](https://rasa.community/library/tutorials/voice-ai-agent/); the tree below remains available as a tutorial-oriented checkout.

---

## Catalog

| Name | Persona | Domain | Path | Assessed on |
|---|---|---|---|---|
| Atlas voice agent tutorial | Atlas | Horizon Travel | [`rasa-voice-agent-tutorial`](rasa-voice-agent-tutorial) | 2026-08-13 |
| Guarding an irreversible action | Wren | Northgate Bank | [`rasa-card-reissue-tutorial`](rasa-card-reissue-tutorial) | 2026-09-02 |
| The document is derived, never written | Ledger | Thornbury Wealth | [`rasa-document-artifact-tutorial`](rasa-document-artifact-tutorial) | 2026-09-02 |

When you add a tutorial, append a row here in the same PR.

---

## How to add a tutorial

1. Follow [CONTRIBUTING.md](../CONTRIBUTING.md).
2. Start from [docs/TUTORIAL-TEMPLATE.md](../docs/TUTORIAL-TEMPLATE.md) — it
   defines the two-repo contract, the opening requirement, and the declared
   step list, and points at
   [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md) for the README.
3. Add the catalog row above.
4. Area review: [MAINTAINERS.md](../MAINTAINERS.md).
