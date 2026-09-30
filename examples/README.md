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

Casebook case builds are named `mantle-<mode>-<case-slug>-<model>`, for example `mantle-text-insurance-policy-status-gemini`: one live agent per casebook case, with the case slug kept whole so the example, the casebook entry and the article about it share one searchable name. Each carries a `case-build/` folder of scripted conversations and recorded live results, run with the shared harness in [`scripts/case_builds/`](../scripts/case_builds/).

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
| HarborCover policy status on Gemini (text) | HarborCover status assistant | Insurance / casebook case build | [`mantle-text-insurance-policy-status-gemini`](mantle-text-insurance-policy-status-gemini) | 2026-09-29 |
| Northgate block card on GPT with Deepgram (browser voice) | Northgate card services | Retail banking / casebook case build | [`mantle-voice-banking-block-card-gpt`](mantle-voice-banking-block-card-gpt) | 2026-09-29 |
| Cedar Clinic refill requests on GPT, speech on the Mac (browser voice) | Cedar Clinic prescription line | Healthcare / casebook case build, self-hosted speech | [`mantle-voice-healthcare-refill-request-gpt-local`](mantle-voice-healthcare-refill-request-gpt-local) | 2026-09-30 |
| Northgate transfers on GPT (text) | Northgate Bank transfers assistant | Retail banking / casebook case build | [`mantle-text-banking-transfer-gpt`](mantle-text-banking-transfer-gpt) | 2026-09-30 |
| Northgate risk step-up on GPT (text, web chat) | Northgate payments assistant | Retail banking / casebook case build | [`mantle-text-banking-risk-step-up-gpt`](mantle-text-banking-risk-step-up-gpt) | 2026-09-30 |
| HarborCover quote and bind on GPT (text) | HarborCover quotes assistant | Insurance / casebook case build | [`mantle-text-insurance-quote-bind-gpt`](mantle-text-insurance-quote-bind-gpt) | 2026-09-30 |
| Juniper Mobile connectivity recovery on GPT (text) | Juniper Mobile connection support | Telecom / casebook case build | [`mantle-text-telco-diagnostics-gpt`](mantle-text-telco-diagnostics-gpt) | 2026-09-30 |
| Willow Shop guided selling on GPT (text) | Willow Shop accessories assistant | Retail / casebook case build | [`mantle-text-retail-guided-selling-gpt`](mantle-text-retail-guided-selling-gpt) | 2026-09-30 |
| Horizon Rewards redemption on GPT (text) | Horizon Rewards chat | Travel loyalty / casebook case build | [`mantle-text-travel-redemption-gpt`](mantle-text-travel-redemption-gpt) | 2026-09-30 |
| Willow Shop order status on Gemini with Deepgram and Rime (browser voice) | Willow Shop order help | Retail / casebook case build | [`mantle-voice-retail-order-status-gemini`](mantle-voice-retail-order-status-gemini) | 2026-09-30 |
| Northgate loan payoff quotes on Claude (text, web chat) | Northgate loan servicing assistant | Retail banking / casebook case build | [`mantle-text-banking-loan-servicing-claude`](mantle-text-banking-loan-servicing-claude) | 2026-09-30 |
| Willow Shop returns and exchanges on Claude (text, web chat) | Willow Shop returns and exchanges assistant | Retail / casebook case build | [`mantle-text-retail-return-claude`](mantle-text-retail-return-claude) | 2026-09-30 |
| Orchard Works step-up authentication on Claude with Deepgram (browser voice) | Orchard Works IT service desk | Internal IT / casebook case build | [`mantle-voice-step-up-authentication-claude`](mantle-voice-step-up-authentication-claude) | 2026-09-30 |
| Northgate advisor appointments on Claude with Deepgram and Rime (browser voice, en-GB caller) | Northgate Bank appointments | Retail banking / casebook case build | [`mantle-voice-banking-advisor-appointment-claude`](mantle-voice-banking-advisor-appointment-claude) | 2026-09-30 |
| Orchard Works IT helpdesk access requests on Claude (text, web chat; Slack target) | Orchard Works IT helpdesk | Internal IT / casebook case build | [`mantle-text-internal-it-helpdesk-claude`](mantle-text-internal-it-helpdesk-claude) | 2026-09-30 |
| HarborCover claim intake on Claude (text, web chat; Microsoft Teams target) | HarborCover claims intake assistant | Insurance / casebook case build | [`mantle-text-insurance-file-claim-claude`](mantle-text-insurance-file-claim-claude) | 2026-09-30 |
| Cedar Clinic pre-visit intake on Gemini (text, web chat) | Cedar Clinic pre-visit intake chat | Healthcare / casebook case build | [`mantle-text-healthcare-intake-gemini`](mantle-text-healthcare-intake-gemini) | 2026-09-30 |

When you add an example, append a row here in the same PR.

---

## How to add an example

1. Follow [CONTRIBUTING.md](../CONTRIBUTING.md) (one resource per PR, must run).
2. Start from [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md).
3. Add the catalog row above.
4. Area review: [MAINTAINERS.md](../MAINTAINERS.md).
