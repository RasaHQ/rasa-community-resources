# Workshop audit and corrections

**Checked 22 October 2026. Verdict: revised teaching materials and corrected scaffold; complete live voice factory not yet demonstrated.**

The original ZIP has 526 files. Review covered the entry points, all nine book chapters, facilitator plans, slide source and rendered deck, dependency manifests, the current travel runtime and its tests, factory driver, and the historical API/SDK examples. All 255 Python files in the revised package parse successfully. Historical fixture outputs are retained as historical evidence, not re-certified against a new engine.

## The decisive gap

The request describes a voice agent that builds and launches a second, visual voice agent. The supplied pack has:

1. A Mantle travel assistant with a source-tool MCP service, graphical cards, optional Deepgram speech, and an optional Agents API source specialist.
2. A separate factory that edits a currency-card Python component using an Agents API builder.
3. Local integration that renders a standalone card.

There is no factory voice skill connected to a build-job MCP service and no demonstrated exact-artifact launch into a new voice assistant. The travel MCP service exposes `find_flights` and `briefing`; its start/get/revise operations manage **briefings**, not software builds. Chapter 7 explicitly says its page does not install the card into the running agent.

The revised materials make that distinction visible. `BUILD-CONTRACT.md` describes the missing integration and 17 acceptance scenarios. It is a specification, not an implemented test suite.

## Findings and disposition

| Priority | Finding in the supplied pack | Correction or remaining work |
|---|---|---|
| Blocker | The advertised voice-to-build-to-voice journey is absent | Clearly disclosed; specified build service, job lifecycle, release worker and acceptance scenarios |
| Blocker | Travel project pins Rasa Pro 3.21.0.dev5 and uses the old `integrations.yml` `llm:` selection | Migrated current scaffold to **3.21.0**, moved selection to `agent.yml` `orchestrator.model_group`, regenerated its lock |
| Blocker | Flux ASR uses `name: deepgram`, which selects Nova in 3.21.0 | Changed to `deepgram_flux`; retained `deepgram` for Aura-2 TTS; validated with installed engine configuration |
| High | Doctor reads old `llm.model_group`; its live Agents probe defaults to gpt-4.1-mini although the pack says that model was refused by the service | Doctor now reads the selected agent group and defaults the Agents probe to gpt-6-astra, matching the supplied worker and official quickstart. Live account access is still unverified |
| High | Current engine requires an AgentSpec in ModelBootstrap and a new resolver signature | Updated doctor probe and relevant fixtures; scripted real-engine conversation passes |
| High | `openai-mcp` imports `Agent` / `Runner` from `agents` and pins `openai-agents` | Explicitly labelled historical **Agents SDK** appendix, removed from main route; current builder uses `client.beta.agents.sessions` through the OpenAI client/Core adapter |
| High | Run sheet, facilitator script and deck describe different agendas and different demos | Replaced with one elapsed-time schedule: 125 minutes of lab and networking |
| High | “Only reviewer: tests” and hidden-tests-as-definition oversimplify the factory | Replaced with independently controlled verification, explicit release policy, monitoring and escalation; secrecy is optional additional protection |
| High | Chapters 3–7 require macOS sandbox-exec, despite a general laptop workshop | Explicit platform selection; working standard-library data-only route for other machines; no sandbox check removed |
| High | ZIP instructions tell participants the ZIP cannot work and reference a different repository layout | Added local `git init` route preserving credential checks, package-relative guide, and corrected book path conventions |
| Medium | Test assumes a `.gitignore` outside the packaged layout | Added package ignore rules and corrected the test's root calculation |
| Medium | Long book estimates total more than the available group time | Selected a shorter route with timed checkpoints; retained full chapters for reference |
| Medium | The card exercise could be confused with building the entire assistant | Explicitly explained scaffold, candidate component and separate integration boundary |
| Medium | Persona says never admit lack of real-time flight access | Replaced with honest source-unavailability behavior |
| Medium | Slide prose repeats “You'll understand”, “In short”, “Next”; elementary examples displace the travel task | Rebuilt 23 slides around concrete travel requirements, failure cases, architecture and evidence |
| Medium | No self-contained current participant entry point | Added participant guide, troubleshooting, checkpoint evidence and group handoff |

## Current APIs: what is verified

**Mantle.** PyPI reports Rasa Pro 3.21.0; the Mantle changelog identifies it as the first official open beta released 20 October 2026. Unreleased changes are not assumed present. The current travel project now validates with zero authoring findings on the installed 3.21.0 engine. This is authoring validation, not a licence check or proof of every runtime path.

**Deepgram.** Some current tutorial/reference snippets still show the older Flux ASR selector. The release changelog says to use `deepgram_flux`; installed 3.21.0 code confirms the distinct Nova/Flux engines and rejects a Flux model under the Nova selector. This revision follows the release and installed engine. It uses Flux recognition and Aura-2 speech synthesis, not Flux TTS. Actual audio still requires a live rehearsal.

**OpenAI.** The current official API documentation uses `client.beta.agents.sessions.create`. Session tools request application work and receive results; attaching an environment does not automatically put application function handlers inside that environment. The worker's OpenAI 3.36.1 / Core 0.36.2 contract tests pass without a provider request. Mantle retains its compatible OpenAI 2.x client in a separate environment. Do not combine those environments or substitute the Agents SDK sample.

The API quickstart names application-key permissions `api.agents.read`, `api.agents.write` and `api.responses.write`; the SDK adds the beta header. Neither a ChatGPT subscription nor a key merely being present proves API access. Model availability remains account-specific.

**Source cards.** Flight position is an observation; the landing time is computed. It is not an airline schedule or evidence of a delay. Weather is a forecast, transfer time is an assumption, and FX is daily reference data. The dashboard is custom application code. Neither Mantle nor the Agents API automatically renders it. The revised slides label their example board as an illustration.

## What was executed here

| Check | Result | Boundary |
|---|---|---|
| Python syntax | 255 files parse | No runtime claim |
| Original project under Rasa 3.21.0 | Reproduced unexpected_llm and missing orchestrator.model_group findings | Confirms the migration was needed |
| Revised project authoring validation | 0 findings | No model, licence or voice request |
| Deepgram configuration tests | 3 passed | Installed schema validation, no audio |
| Doctor / credential controls | 18 passed | Synthetic credentials only |
| Launcher tests | 46 passed | Includes real channel parsing; no full live launch |
| Mantle hook tests | 8 passed | Validated output hooks, synthetic source data |
| Scripted Mantle conversation | 1 passed | Actual orchestration + in-process MCP + replay cards, scripted model replies |
| Installed native Agents contract | 3 passed | Actual SDK/Core surface, injected transport, no billed API call |
| Released source integration | 1 passed | Core 0.36.2, MCP and injected provider responses, four cards |
| Cross-platform teaching logic | 3-attempt and 1-attempt paths pass | Accepted proposal, rejected baseline, recovery, duplicate suppression; Linux/Python 3.12 execution only |
| Full Mantle-environment suite | 184 run: 179 passed, 4 failed/error, 1 skipped | Unix sockets denied here; one process teardown failure also remains; see final log |
| Slides | 23 rendered; 1600×900 and 1280×720 layout/navigation checks pass; no network asset requests | Visual review performed; PDF has 23 pages |

The initial broad test run in the worker-only environment did not pass: it included Mantle-dependent tests and Unix-domain-socket tests unsupported by this host. These were not relabelled as successes. Relevant tests were then run in the appropriate environment, with results above. The final full-suite run has three failures associated with Unix socket control and one process-group teardown error; the latter passed in the isolated launcher suite but remains unresolved in the combined run. The complete `make test`/launcher lifecycle and browser microphone path still need the intended workshop machine. See `verification/` for selected raw results and the final suite status.

## What remains unverified

- Live Rasa licence acceptance and real microphone / speaker behavior.
- A paid Agents API session, this account's model access and actual cost.
- Current flight, forecast and exchange-rate service availability.
- Fresh setup and full launcher lifecycle on the facilitator's Mac; Unix-domain sockets are denied on this execution host.
- macOS sandbox-exec factory chapters and actual live-built artifact integration.
- The complete factory voice interface, durable build jobs, cancellation, automatic release and rollback.
- Native Windows launcher support. The JSON recovery route is portable in design but was executed here on Linux only.

No provider credentials were requested or used, and no billed provider run was performed.

## Teaching and brand changes

The deck retains Rasa's warm cream/ink composition, uses the official horizontal logo and documented open fallback fonts (Newsreader, Inter, JetBrains Mono). Pink marks emphasis. Status is always expressed in words, not color alone. The new deck includes concrete travel examples, API/SDK distinction, build-time versus run-time architecture, group instructions and presenter notes. It is a brand adaptation, not a newly approved corporate template.

The main session ends its teaching at minute 40. Lab A is 55 minutes, networking is 15, Lab B is 55. Groups finish with one requirement, one rejection, one accepted output and one limitation. Statistical confidence intervals and historical compiler defects move out of the main route.

## Source references

Checked 22 October 2026. These are external references, not vendored documentation.

- Mantle overview: https://mantle.rasa.com/
- Mantle changelog: https://mantle.rasa.com/changelog
- Agent configuration: https://mantle.rasa.com/reference/agent-yml
- Runtime integrations: https://mantle.rasa.com/reference/integrations-yml
- Speech provider reference (contains older examples; use release-specific verification): https://mantle.rasa.com/reference/speech-providers
- PyPI release metadata: https://pypi.org/pypi/rasa-pro/json
- Agents API overview: https://developers.openai.com/api/docs/guides/agents-api/overview
- Agents API quickstart: https://developers.openai.com/api/docs/guides/agents-api/quickstart
- Session lifecycle: https://developers.openai.com/api/docs/guides/agents-api/sessions
- Function tools: https://developers.openai.com/api/docs/guides/agents-api/tools/functions
- Rasa brand system and exact logo asset: https://github.com/RasaHQ/brand ; `assets/logos/digital/rasa-logo-horizontal-ink.svg`

Historical results remain tied to the old project pins. Their presence in this package does not certify current behavior. The original top-level plans and slide source are preserved under `archive/2026-10-22-original/`.
