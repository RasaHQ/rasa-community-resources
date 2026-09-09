# Verification record — 2026-09-08

- Offline suite: seven test methods pass. The all-scenarios method checks 62
  cases, 620 expected input outcomes and 186 predicate-deletion mutations, plus
  persisted replay, lost acknowledgments and receipt reconciliation per case.
  Other methods cover concurrent requests, cross-case/revision conflicts,
  unknown records, strict boolean authority and malformed identifiers.
- Installed project: `uv sync --prerelease=allow` succeeds with the committed
  lock, Python 3.12.13 and the repository's pinned engine.
- Rasa configuration: `rasa.mantle.validation.validate_project(Path('.'))`
  succeeds against the installed engine and loads the scenario skill and all three
  declared tools.
- Direct adapter checks: the real Mantle ToolResult SDK returns and replays
  synthetic receipts for all 62 scenarios, plus four independent intakes.
- Live conversation, speech and external service validation: not performed by
  this record. Offline results are finite synthetic checks, not estimates of
  production reliability or measured human satisfaction.

Run `make proof` to reproduce the offline checks and `make validate` to validate
configuration. Keep sampled model observations in a separate record with the
actual model/version, inputs, trace and resulting state.
