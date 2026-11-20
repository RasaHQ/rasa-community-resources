# Changelog

Changes are grouped by month because this repository has no release tags.

## Status — 2026-11-20

Rasa Community Resources contains runnable examples, reusable patterns and workshop material for building conversational agents with Rasa.

- **Activity:** active. The last meaningful source change was November 20, 2026. There are no releases yet.
- **Available:** locked example projects, local mocks, offline tests, a resource catalog and project-specific development containers.
- **Limits:** real model and speech calls require the reader's own access. Some banking examples also require separately supplied interface definitions. A mock or offline test is not a live banking result.
- **Check:** run `make validate STRICT=1` for the offline repository checks. Each project's README describes its own setup and tests.

## [2026-11]

### Added

- Self-contained banking examples include fictional state, typed requests and replies, local contract mocks and confirmation tests.
- A Telegram shop assistant supports order setup, review, confirmation and status using a spreadsheet-backed example.
- A release-specific speech profile demonstrates a transfer conversation with a pinned runtime and separately scoped text and voice checks.
- Runnable resources have project-specific development-container launch links and clearer prerequisite checks.
- A travel-agent workshop includes locked environments, printed setup guidance and exercises for flight and weather lookup.
- Billing exercises retain conflicting observations so readers can investigate an uncertain result instead of replacing its history.

### Changed

- Banking walkthroughs share a beginner-friendly structure, with explicit setup, expected behavior and limits.
- Vendor-definition checks track the supported version of each example and distinguish compatible changes from ones that need review.
- Runtime migration checks cover both supported release lines while keeping the general catalog pin separate from experimental profiles.
- Setup commands explain missing configuration and the next step before starting the shop or banking assistant.
- The resource catalog is generated from the maintained projects and records their available checks.

### Fixed

- Corrected travel dates and local clock times before weather lookup, including ambiguous flight records and arrivals after midnight.
- Preserved failure statuses from readiness and snapshot-selection commands.
- Fixed tool dispatch, isolated dependency environments and graceful shutdown in the shop and banking examples.
- Delivered short confirmations and final speech transcripts once, without turning duplicate events into new requests.
- Kept uncertain transfers and canceled reviews distinct from completed submissions.
- Clarified which speech and text results were actually checked and which behaviors still need a separate test.

### Security

- Bound banking reads, reviews and confirmations to their originating user and session.
- Strengthened workspace isolation, local service identity checks and uncertain-write handling.
- Bound Telegram setup to a fresh private-chat challenge and rejected unsuitable activity files safely.
- Kept configuration values private during setup and diagnostic output.

### Removed

- Replaced the old router workshop with the travel-agent factory course and removed obsolete generated course copies.

## [2026-10]

### Added

- Framework-composition examples retain existing workflow, retrieval, memory and media components while adding a Rasa conversation.
- A SQL migration example includes shared tools, bounded results and controls for refused requests.
- Exercises cover tool confirmation, saved handoff evidence, account selection and changes after approval.
- A software-factory course includes a book, diagrams, slides, scripted exercises and optional live builders.
- Travel examples support flight discovery, local destination times, validated source cards and optional voice input.
- Community projects add complaint handling, energy advice, development assistance, nutrition, notes and skill evaluation.
- Isolated workspace tooling keeps project environments and retained evidence separate.

### Changed

- Shared voice routing supports more tutorial frameworks while keeping provider configuration explicit.
- Course material distinguishes scripted demonstrations, recorded runs and optional live work.
- Pull-request checks focus on the relevant offline validation, with broader checks retained for their documented workflows.
- Project discovery distinguishes maintained examples from frozen contributions and ignores installed environments.

### Fixed

- Serialized shared speech connections and fixed turn completion, playback waiting and cancellation behavior.
- Corrected tool packaging, interpreter selection, pinned dependencies and cold-start imports.
- Rejected stale account proposals and kept specialist memory and dialogue tied to the intended conversation.
- Made result budgets, refusal reasons and source freshness visible to the caller instead of inventing defaults.
- Preserved newer travel displays when an older background job finished later.

### Security

- Restricted local demonstration services and validated display and worker requests before accepting results.
- Redacted configuration values from diagnostic capture and kept offline checks separate from live credentials.
- Bound approval and cancellation to the original request and worker.

## [2026-09]

### Added

- A starter pack includes agent-building guidance, reusable skills and evaluation examples.
- Voice-routing patterns support provider switching, local speech options, failover and retained routing state.
- Reusable patterns cover step-up authentication, stateful handoff and documents derived from recorded state.
- Casebook examples cover banking, insurance, retail, utilities, travel, healthcare and education.
- A shared conversation harness supports text and browser voice, repeatable scenarios and separate provider-error reporting.
- A three-framework voice tutorial shares domain tools, a conversation specification and usage recording.
- Frozen community contributions and cohort examples are indexed separately from maintained projects.

### Changed

- **Breaking:** moved the orchestrator model settings into a named model group for Rasa 3.20.0.dev6. Project memory is now written by tools rather than directly by the model.
- **Breaking:** replaced removed skill-level `requires` settings with preconditions or hidden skills for Rasa 3.21.0.dev2. Tool-level approval settings remain separate.
- **Breaking:** changed model-group credentials from `api_key_env` to environment references in `api_key` for Rasa 3.21.0.dev2.
- Automated release proposals retain tested compatibility evidence and preserve manual repair work.
- Generated catalogs connect each example to its instructions and recorded runs.

### Fixed

- Corrected router cooldown, asynchronous speech interfaces and WebSocket option compatibility.
- Distinguished a customer's correction from a declined recovery step and kept saved state within runtime limits.
- Fixed output hooks so confirmed tools remain visible while refused or future requests are handled accurately.

### Security

- Required explicit confirmation for sensitive actions and prevented alternative channel paths from weakening the same approval rule.

## [2026-08]

### Added

- Established the resource catalog with examples, tutorials, reusable patterns, contribution guidance and migration tooling.
- Added CRM, session-personalization and voice examples with setup instructions.
- Added lint checks for version consistency, configuration and pinned workflow dependencies.

### Changed

- **Breaking:** migrated engine imports from `rasa.calm_v2` to `rasa.mantle` for Rasa 3.20.0.dev1 and raised the supported Python floor to 3.11.
- Kept the examples on a shared supported Rasa version.

### Fixed

- Corrected agent configuration nesting so the engine reads the declared prompts and settings.
- Kept frozen community projects separate from bulk version migrations.
