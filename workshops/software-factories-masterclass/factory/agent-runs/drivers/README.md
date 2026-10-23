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
python agent-runs/drivers/openai_factory_driver.py TASK.json PREPARED_SCRATCH NEW_RUN --model MODEL --no-session-cap --expected-cost-cents-min MIN --expected-cost-cents-max MAX
python factory_console.py NEW_RUN --port 8943
```

The console can start against the future run path before the driver starts.
It reads only the named evidence artifacts: `console.json`, `events.jsonl`,
`review/change.patch`, `review/review.json`, `verification/decision.json`, and an
validated owner-returned `integration.json`. It has no write or execution endpoints and
never serves arbitrary files or raw SDK logs. The factory's existing decision,
not the builder's successful tool calls, supplies ACCEPT or REJECT. Integration
is recorded by the product owner; this driver does not restart a product or
invent an integration result.

A trusted receiving program can pass `execute(..., integration_hook=callable)`.
There is no CLI, model-supplied import, command or callback path. The callable
receives only the resolved run-directory `Path`, once, after a completed successful
native turn, factory exit 0, a protected ACCEPT decision and a fresh digest match
against the collected candidate. Reusing the run directory is refused. Without
a hook, `integration.json` explicitly stays `NOT_RECORDED`, including on native
failure or a non-ACCEPT gate; none of those paths invokes a receiver.

The returned record has exactly these fields: `schema` equal to
`rasa.factory-integration/v1`; `status` equal to `NOT_RECORDED`, `FAILED` or
`APPLIED_RESTARTED`; matching `candidate_digest`; `baseline_head` and
`integrated_head` as full hexadecimal Git identifiers or null; `receipt_ref` as
a bounded single-line path/reference or null; and a lowercase underscore
`reason_code` of at most 64 characters. `APPLIED_RESTARTED` requires both heads
and a receipt reference. Unknown fields, invalid types, digest changes and
credential-bearing records fail validation. Callback exceptions produce only
`FAILED` / `integration_hook_failed`, without exception text or retry. Writes
refuse a symlink at the integration artifact.

If the integration artifact cannot be written after protected ACCEPT, the
driver preserves the factory's exit code and records `FAILED` /
`integration_record_write_failed` in `console.json`. The viewer gives that
failure precedence over an older integration artifact, including a previously
written `APPLIED_RESTARTED` assertion. The receiver is not retried, and raw
filesystem exception text is not recorded.

The protected factory exit code remains its own verdict. Inspect the separate
integration status: an ACCEPT with a FAILED receiver is not a product success.
The receiver is trusted host code and must bound its own synchronous apply,
restart and HTTP checks. This bridge validates its assertion, not the product
evidence itself. Only the receiving owner supplies an actual baseline and HTTP
receipt; no injected test record is proof of the classroom end-to-end journey.

The model gets only `list_files`, `read_file`, and `write_file`. Every file is
opened relative to the scratch directory descriptor, with symlink/hardlink and
special-file refusals, task-path checks and byte limits. Hidden files and the
protected suite are unavailable; no shell or network tool is registered.
One `run_native` call has 30 tool calls, 10,000 events, a 120-second deadline
and a 20-second transport timeout. It uses `environment={"type":"none"}` so no
hosted shell/network is implicitly granted; this environment with function tools
still needs the owner’s bounded live qualification. There is no automatic
fallback. The CLI requires `--no-session-cap` and an expected cost range in USD cents,
stated before execution. There is no per-session money cap. An account owner can configure an enforced hard project or organization spend limit; a budget alert alone does not stop traffic. Enforcement can lag slightly, so recorded spend may exceed that configured amount. See the [spend-limit guide](https://developers.openai.com/api/docs/guides/spend-limits). The
provider rejected `spend_control` in a bounded consuming run on 2026-10-22;
this driver never sends that field, including through Core 0.35.4.
Use one named model, no retry loop and the local bounds above. Run at most
three funded builder sessions during a rehearsal.
Keep a rehearsal session ledger and inspect the actual usage afterward. Do not
substitute an invented price estimate: the MIN/MAX arguments must be supplied
from the facilitator's stated plan. These numbers are expectations, not caps.
An optional `--spend-limit-cents LIMIT --estimated-cents-per-call ESTIMATE`
checks `30 * ESTIMATE <= LIMIT` locally before a request. Both must be supplied
together; this is caller-provided estimation only and sends no spend parameter.
No paid run or observed live cost is claimed by this source qualification.
A failed, cancelled, incomplete or unrecorded session stops with exit 2 and BUILDER_INCOMPLETE: it cannot collect or ACCEPT a partial change. Only a completed session proceeds. The host then invokes the existing
`collect.py` and `factory.py`, preserving exit codes 0–4. The prepared scratch
must contain the visible task and `.scratch.json`; a repository checkout or
workspace containing acceptance files is refused.

For the temporary class preview, pass the actual tailnet address at runtime
with `--host` and an aware `--expires-at` no later than the authorized class end.
Declare `--viewer-access operator-device-acl` or `operator-accepted` for a tailnet preview. This declaration does not enforce a device ACL; the actual audience restriction remains a separate operator/network control. No tailnet hostname or address is committed. Localhost is the default; public
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

For the chapter's task B, the public task also contains a validated currency
limit from 1 to 3. It is visible in the scratch task and native prompt; protected
paths and fingerprints remain excluded. The verifier gets its own exact host
task snapshot beside the protected tests. The offline qualifier accepts
`--task TASK --scripted-candidate ATTEMPT` for that ready folder.

The read-only viewer can compare up to four explicit prior teaching run
directories with repeated `--comparison-run DIRECTORY`. These paths are host
configuration, never URL parameters. The page shows their actual decisions and
reasons as separate offline teaching attempts, without claiming model results.

The A6 verifier requires macOS sandbox-exec. The profile declares this
requirement; missing support returns exit2 before any model request or test,
without judging the attempt.

The native request explicitly selects Standard processing (`service_tier=default`)
so its stated price assumptions are reproducible. After Core returns and file
tools close, the driver makes at most one read of its own session metadata,
with a 20-second timeout. `usage.json` keeps only numeric token counts, a known
service tier and any best-effort consumed-cents value. It stores no session ID,
provider text or headers. SCRIPTED runs make no metadata request.

Usage is best effort and may be absent or change. `actual_billed_cost_cents`
remains unrecorded: API consumption and a rate-based calculation are not a final
invoice. Reconcile the account usage separately. A refused metadata read keeps
only its HTTP status and bounded code/parameter/type; it does not trigger a
retry or change the protected decision. Core's bounded provider detail is also
retained for failed native sessions, without the raw exception message.
