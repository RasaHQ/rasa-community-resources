# Patterns

Small, focused reference implementations of problems that recur when building and operating Rasa agents — tool design, evaluation harnesses, deployment shapes, observability, human handover, and similar.

This folder is **accepting contributions**.

| Pattern | Problem it solves |
|---|---|
| [`session-start-personalization`](session-start-personalization/) | The default greeting is anonymous. Load what you know about the customer before the first word, then spend it later in the conversation. [Guided walkthrough](session-start-personalization/tutorial/TUTORIAL.md). |
| [`voice-vendor-router`](voice-vendor-router/) | One vendor's outage should not mute or deafen a live call. Give ASR and TTS a chain of providers instead of one, and fail over on what the error meant — keeping the caller's voice unless credits, credentials or reachability actually went. |
| [`evaluation-harness`](evaluation-harness/) | You changed a prompt and do not know whether the agent got better. Measure it three ways — deterministic tracker assertions, dialogue understanding tests, and LLM-as-a-judge scoring — and know which one answers which question. |

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
| voice-vendor-router | Swap and fail over between ASR/TTS vendors so one provider outage cannot mute or deafen a live call | [`voice-vendor-router`](voice-vendor-router) | 2026-09-02 |
| session-start-personalization | Personalize every conversation by resolving identity once, at session start, into shared project memory | [`session-start-personalization`](session-start-personalization) | 2026-08-25 |
| evaluation-harness | Measure whether a change to an agent helped, using assertions, dialogue understanding tests, and LLM-as-a-judge scoring | [`evaluation-harness`](evaluation-harness) | 2026-09-02 |

---

## How to add a pattern

1. Follow [CONTRIBUTING.md](../CONTRIBUTING.md).
2. Start from [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md).
3. Replace the empty catalog row with your entry.
4. Area review: [MAINTAINERS.md](../MAINTAINERS.md).
