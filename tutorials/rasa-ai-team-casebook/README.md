# AI team casebook lab

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-rasa-ai-team-casebook/devcontainer.json)

- **You need:** nothing for the first command, which needs no license and no network. Later steps use the free Rasa Developer Edition license and the keys named: `RASA_LICENSE`, `OPENAI_API_KEY`, saved once as personal Codespaces secrets ([how](../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `python3 casebook.py --case contextual-handoff --prove`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** ten observed fixtures printed; this one needs no license and no network.
<!-- codespaces:end -->

Author:        Rasa Community
Assessed on:   2026-09-08
Assessed by:   Codex Principal (offline checks; runtime scope recorded below)
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv  # rasa-version-ignore: historical assessment; current checks in COMPATIBILITY.json
Installation:  rasa-pro 3.21.0.dev5 (automated check scope in COMPATIBILITY.json)
Audience:      AI teams rehearsing evidence, authorization and recovery boundaries
Time:          20–40 minutes per case; optional model integration takes longer

This project accompanies 62 fictional scenarios, each with six role exercises.
It is a shared **synthetic evidence lab**. It does not implement a bank, clinic,
carrier or other external service. The lab exposes the point where a proposed
action, its trusted authorization evidence and its service receipt differ.

## Start without a licence or network

Use Python 3.11 or later. Run from this directory:

```bash
python3 casebook.py --case contextual-handoff --prove
make proof
```

The first command prints ten observed fixtures, including false, missing and
string-valued facts, and the predicates whose deletion the oracle detected.
The suite exercises all 62 scenarios, persisted retries, concurrent requests,
lost acknowledgments, changed request identities and receipt reconciliation.
A test exit of zero establishes these finite synthetic checks only.

## See a pending outcome survive a retry

```bash
python3 casebook.py --case contextual-handoff --request-id handoff-1 --lose-ack
python3 casebook.py --case contextual-handoff --request-id handoff-1 --lookup
python3 casebook.py --case contextual-handoff --request-id handoff-1
```

The first result is pending with reason `acknowledgment_lost`. The second looks
up a succeeded synthetic receipt. The third replays the same `LAB-` reference;
it does not add another row. The SQLite file persists across all three commands.
Choose a new identifier only for a deliberately new request, after resolving
any prior pending outcome. A `no_local_record` lookup describes this lab’s database. Check the remote service’s outcome separately before resubmitting.

For a receipt that remains unverified, copy a scenario's `facts` object into a
separate JSON file, set one receipt-phase field to false, then pass
`--facts path/to/facts.json`. Expect pending with one stored synthetic effect.
After the simulated owner supplies corrected receipt evidence, run the same
case and identifier with `--reconcile --facts path/to/corrected.json`. This
updates the existing row and never creates an action. Reconciliation is an
operator lab command; the model has no reconciliation tool.

## What the architecture establishes

`examples/*.json` contains an authored policy contract and materialized expected
outcomes. Request-phase evidence is checked before the synthetic action row;
receipt-phase evidence determines whether that row supports a succeeded outcome.
The boolean facts are already adjudicated fixture facts. The program does not
verify identities, parse policies or establish clinical correctness for you.
Each scenario identifies the evidence a real adapter must resolve and its owner.

SQLite performs lookup and the synthetic action in one transaction. This models
atomic local idempotency, **not a distributed transaction** with an external
provider. A real adapter needs the provider's idempotency guarantee, durable
outbox/reconciliation and authenticated context. Copying this local transaction
around a network request does not confer those guarantees.

`tools/cases.py` accepts only a supported case identifier. It reads facts from
the trusted local fixture and binds the request to operator-set `CASEBOOK_RUN_ID`.
It never accepts model-provided authorization, receipt validity or retry IDs.
The fixed identity is for this single-operator rehearsal; production identities
must bind an authenticated subject, action, target and revision. No real customer
identity, secret or payload belongs in these fixture files.

## Optional Rasa conversation observation

Install the pinned dependency, copy `.env.example` to `.env`, fill in your own
`RASA_LICENSE` and `OPENAI_API_KEY`, then run:

```bash
make install
make validate
make train
make chat
```

Use a supported identifier, such as `contextual-handoff`. Ask for its state,
correct the requested case, and test how the agent describes a pending outcome.
Record the model/configuration version and actual tool trace. These observations
are sampled model behavior and remain separate from the offline test result.
The version in the metadata identifies the pinned engine target; `VERIFICATION.md` records the completed runtime checks.

## Case and role index

The accompanying site provides one exercise per case for product, engineering,
conversation design, evaluation, operations and domain/risk review. The scenario
files here are the executable source of their evidence tables. Read `INDEX.md`
for all cases and the distinct failure each one teaches.

## Required secrets and licence

Offline exercises require no secrets. Optional model observation uses your own
`RASA_LICENSE` and `OPENAI_API_KEY`; never commit `.env`. Teaching code follows
the repository's [Apache 2.0 licence](LICENSE). Rasa Pro has separate terms.

## Independent intake is a separate transition

Four cases preserve an observation or request even when a later guarded action
cannot proceed: driver arrival, absence reporting, cancellation and unmatched
outage reporting. Choose that route explicitly:

```bash
python3 casebook.py --case internal-shift-swap --request-id absence-1 --intake
python3 casebook.py --case internal-shift-swap --request-id absence-1 --lookup-intake
```

The first result has `status: recorded`, an `INTAKE-` reference and zero guarded
actions; lookup returns the same record. A refused swap cannot remove that
absence. Track arrival, loading clearance, cancellation requests, account closure, outage observations and restoration times as separate service records. The model has a separate `record_case_intake`
tool for this confirmed choice; presenting an offer never silently cancels it.

## Check what the appointment booleans leave out

Run `python3 -B appointment_binding_demo.py`. It changes the confirmation question while keeping the three adjudicated facts true. The lab replays its original record. Adding an explicit channel is refused as `unknown_fact`: this generic lab models rule outcomes, while a real booking adapter must bind the actual channel, purpose and slot to the confirmed request. The script also checks that the two explicit appointment payloads have different hashes. All values and database actions are synthetic; the temporary database is removed after the check.


## Reconcile separate billing observations

Assessment of this added exercise: Rasa Community (Codex), 2 November 2026;
Python 3.14.3, nine billing tests and 28 casebook tests passed. The commands
below require only the standard library; no Rasa runtime was exercised.

Run this read-only exercise with Python 3.11 or later, without installing Rasa:

```bash
python3 -B billing_reconciliation.py
python3 -B -m unittest discover -s tests -p test_billing_reconciliation.py -v
```

The fixture has two revisions each for one payment, invoice and policy, all for
one synthetic account and policy. Across all 720 delivery orders, the reducer
selects each source's highest revision and reports settled, paid and active.
An intentionally defective comparison freezes the first invoice and infers
policy status from its label. It disagrees in 360 orders. These are exhaustive
permutations of six invented observations, not sampled production error rates.
The nine tests also cover missing policy data, duplicates, older revisions,
contradictory revisions, wrong account/policy and invalid inputs. A settled
payment does not override a policy service observation that says lapsed.

The reducer checks scope and source-specific state names. Revisions are ordered
only within one source. Contradictory observations at the same revision put the
report into investigation, including when that revision is older than the
current one. Later observations do not clear a conflict automatically.

This is a source-selection model, not a service adapter or coverage decision.
It trusts its fixture source identities and monotonic revision numbers. It has
no signature, freshness deadline, payment-reference lookup, persistence or
cross-service snapshot transaction. The permutation check reads the final report after all six messages arrive.
Before replying during delivery, a live adapter needs an observation-age limit
and a consistency contract agreed with its service owners. This module
never charges a customer, changes coverage or instructs a payment provider.

Calendar manuscript: the held insurance-billing case will use this exercise
only after independent source and editorial review. No publication approval
or release date is implied by adding the companion code.
