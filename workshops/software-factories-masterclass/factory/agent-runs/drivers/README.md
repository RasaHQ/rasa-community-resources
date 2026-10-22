The scripts that produced the recorded runs, as they ran. `run_claude_experiment.sh` made the nine Claude Code runs. `run_one_codex_and_claude.sh` made the nine Codex runs (called nine times from a loop `for n in 1 2 3; for t in a1-block-card a2-rule-digits a3-rule-confirm; ./run_one.sh codex tasks/$t.json $n`); its folder and virtual-environment paths are now the variables `MF_DIR` and `MF_VENV` (see `../NOTE.md`), and it is a record, not a tool. Besides the two path variables, one more edit: `run_one_codex_and_claude.sh` had a no-op `for k in OPENAI_API_KEY RASA_LICENSE; do :; done` that looked like a scrub and did nothing; it is now a comment saying how the agents authenticated (their own stored sign-in; `OPENAI_API_KEY`, `RASA_LICENSE` and `ANTHROPIC_API_KEY` were unset in the shell when checked). The Claude Code script was started with `env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT ...` from a detached tmux session.

## Managed Agents builder and factory console

sow: software-factories-masterclass-SOW-02

`openai_factory_driver.py` is a current driver alongside the preserved historical
scripts above. Give it a task, a workspace already prepared by `scratch.py`, a
NEW run directory outside that workspace, and an explicit model. Run it with
the maintained native-worker interpreter that supplies Core's `run_native` and
the supported managed Agents SDK. `OPENAI_API_KEY` is process-only; no key is
accepted on the command line. The client uses the first-party API, no ambient
proxy or alternate base URL, and no SDK retry.

```sh
python agent-runs/drivers/openai_factory_driver.py TASK.json PREPARED_SCRATCH NEW_RUN --model MODEL --spend-limit-cents 200
python factory_console.py NEW_RUN --port 8943
```

The console can start against the future run path before the driver starts.
It reads only the named evidence artifacts: `console.json`, `events.jsonl`,
`review/change.patch`, `review/review.json`, `verification/decision.json`, and an
owner-written `integration.json`. It has no write or execution endpoints and
never serves arbitrary files or raw SDK logs. The factory's existing decision,
not the builder's successful tool calls, supplies ACCEPT or REJECT. Integration
is recorded by the product owner; this driver does not restart a product or
invent an integration result.

The model gets only `list_files`, `read_file`, and `write_file`. Every file is
opened relative to the scratch directory descriptor, with symlink/hardlink and
special-file refusals, task-path checks and byte limits. Hidden files and the
protected suite are unavailable; no shell or network tool is registered.
One `run_native` call has 30 tool calls, 10,000 events, a 120-second deadline
and a 20-second transport timeout. It uses `environment={"type":"none"}` so no
hosted shell/network is implicitly granted; this environment with function tools
still needs the owner’s bounded live qualification. There is no automatic
fallback. A requested provider-side spend cap of 1–200 USD cents is required
(USD 2 requested maximum); the driver refuses before a session if Core lacks `spend_limit_cents`.
Core 0.35.4 exposes that parameter; Core 0.35.2 alone does not. The
request field is verified from the released SDK and official API reference;
the service rejected this field in the consuming owner’s bounded run on 2026-10-22 (HTTP 400, unknown spend_control). No funded retry is authorized by this driver; the live path awaits an explicit replacement-budget ruling. No expected
or observed live cost is claimed yet. A failed, cancelled, incomplete or unrecorded session stops with exit 2 and BUILDER_INCOMPLETE: it cannot collect or ACCEPT a partial change. Only a completed session proceeds. The host then invokes the existing
`collect.py` and `factory.py`, preserving exit codes 0–4. The prepared scratch
must contain the visible task and `.scratch.json`; a repository checkout or
workspace containing acceptance files is refused.

For the temporary class preview, pass the actual tailnet address at runtime
with `--host` and an aware `--expires-at` no later than the authorized class end.
No tailnet hostname or address is committed. Localhost is the default; public
and wildcard binds are refused. The preview shuts down at its expiry. Anyone
who can reach the listener can read the displayed run evidence.

Offline controls:

```sh
python -m unittest discover -s . -p 'test_*factory*.py'
```

These injected native-boundary and real local filesystem/HTTP tests are not a
live managed Agents result. The A6 task/protected suite, three-card prepared
baseline, accepted integration hook and exact supported worker/API contract
remain consuming-owner inputs; final qualification must bind the integrated
head, protected gates and actual native-worker run.

The A6 nested pack is selected with `--pack-root` and the host verifier profile
with `--environment environment-a6.json`. The existing `scratch.main`,
`collect.main` and `factory.main` have optional pack-root adapters; defaults
retain the banking exercises. For A6 preparation, pass the pack root and
`instructions="AGENTS-a6.md"` to `scratch.main`. The gate checks the existing
pinned files and task scope, runs the protected suite with `PRODUCT_PROJECT`
and strict nonzero unittest completion, and does not execute candidate tests
outside the protected sandbox. The profile is a compatibility window; the
actual distribution versions and profile hash are recorded, while installation
still belongs to the receiving owner’s pinned worker environment.

Observed offline qualification: the actual A6 pack’s good candidate ACCEPTs and all three teaching candidates REJECT with the qualified Core worker. The labelled SDK-shaped stream also traverses actual Core 0.35.4, confined file writes, collection and the real protected gate with ACCEPT, without a provider call. Run that control with a fresh evidence directory:

```sh
python agent-runs/drivers/qualify_scripted_builder.py A6_PACK NEW_EVIDENCE
```

This is SCRIPTED teaching code, not a model result. The console labels it accordingly. Remaining end-to-end qualification: bind the product owner’s gated-diff integration hook
to a scripted builder → real factory ACCEPT → actual briefing HTTP restart
regression. A generic injected callback or the console page is not that F7 proof.

The official [create-session reference](https://developers.openai.com/api/reference/python/resources/beta/subresources/agents/subresources/sessions/methods/create)
defines `spend_control` in USD cents and requires initial input with environment
`none`. The [session guide](https://developers.openai.com/api/docs/guides/agents-api/sessions)
distinguishes a completed turn from a successful tool result. These describe
the API contract; the factory’s acceptance still comes from its protected checks.
