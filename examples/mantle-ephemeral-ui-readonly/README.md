# Fixture-first connection-status card (in progress)

Author: rasa-community-maintainer
Assessed on: pending qualification
Assessed by: none; fixture consumer tests only
Verified with: no installed Mantle or Core runtime yet; source targets the repository pin
Audience: Developers connecting a retained tool result to a read-only user interface
Time: Fixture tests take seconds; live setup requires an owner-present session

sow: ephemeral-ui-readonly-SOW-01

This is an **unfinished fixture-first pilot**, not a connected demonstration.
It implements a consumer boundary and a Mantle tool entrypoint. It does not yet
install an agent host, call the Broker, or claim an actual Mantle turn. The
authenticated host integration and producer result contract are still required.
Do not deploy or treat synthetic results as evidence of a real connection.

## What the consumer does

The host allocates one `TurnView` per authenticated conversation and calls
`begin` on **every** new turn, including turns without a tool call. This clears
the old display immediately. Each read carries a host-generated lease and exact
operation/invocation binding. Older completions cannot overwrite a newer turn.
An error on the current turn replaces the old card with an unavailable message.
The authenticated host must allocate a unique invocation for each actual read,
bind it to that conversation's governed original result, and prevent model input
from supplying either reference. Equality against model-supplied IDs proves no
provenance. The host's asynchronous read must honor cancellation and use bounded
transport timeouts. Read plus validation share a nine-second budget, below the
ten-second tool timeout; validation runs outside the event loop. Timeout or
cancellation revokes the display lease, including for a late validation worker.

The `show_connection_status` tool takes no model-supplied identifiers. Its
authenticated host binds `Services` through `bind_services` for that turn.
The injected producer performs one permitted read, retains its original result,
and returns a `RetainedRead`. Rendering never calls the Broker again. The host
mounts the returned `view.html` in its current-turn container; no persistent
storage is used. The host must also clear that container when beginning a turn.
There is deliberately no default global session, credential lookup or live route.

The first real action selected by the Architect is authenticated
`GET /v1/connections`, with **one visible connection and zero operation grants**.
A newly paired device can return an empty list until its owner grants its
application a connection and assigns the device. Empty is honest, but it does
not pass the chosen nonempty acceptance. `labels.list` and `messages.read_page`
are excluded. A refusal stops the read; never substitute another identity.

## Validation and rendering

### Trusted worker client

The authenticated host can bind `WorkerServices(view, worker)` with
`bind_services`. `WorkerClient` consumes the producer's closed
`zeoconnect.poc-worker/v1` pipe protocol. Its launcher and interpreter must be
absolute host-owned, qualified paths; the launcher constructs the producer
with the dedicated caller, session store and approved validator. This example
does not supply those identities or a default launcher. Construct the client
off the event loop, with an isolated environment, before a tool turn.

Keep one `ConversationBudget` per authenticated conversation, including across
worker replacement. It permits eight attempts in total and rejects invocation
reuse. Do not create a fresh budget after failure. The reuse check is scoped
to that conversation; the producer must ensure invocation uniqueness across
conversations. The client requests an actual reservation before binding the
invocation to the cleared view, reads once, validates
through Core and checks retention without another discovery request. The
displayed facts name service, status and advertised operations; advertised
operations are not application grants. There is no provider field or SDK upgrade.

The worker path shares a seven-second monotonic deadline across reservation,
read, consumer validation and retained-original lookup. Failure, cancellation
or a superseding turn revokes the view lease, kills the owned worker process
group (including its validator descendants) and reaps the direct worker. The separate consumer
`CoreProcess` also observes that deadline and cancellation before reaping its
own process group. Cleanup has a bounded grace period below the ten-second
tool timeout. Arbitrary synchronous validators that ignore the budget are not
supported. Call `worker.close()` when the conversation ends; call `view.begin`
on every turn, including turns without a tool, to clear the previous card.
The execution owner must independently verify final namespace quiescence;
reaping a direct child alone is not that receipt.

If the environment denies a cleanup signal, the client closes its local pipe
ends, records `UNKNOWN_SIGNAL_PERMISSION_DENIED`, and raises
`WorkerCleanupError` to the host. It retains the process handle and original
failure; startup errors remain attached when cleanup also fails. It does not
retry the signal, switch cleanup methods, or claim the process exited. The
host must retain this unresolved ownership record and obtain a supported
resolution from the launch venue's permission owner. The Mantle tool reports
only unavailable; its host can inspect `cleanup_error` and `cleanup_state`.

The subprocess fixtures test this client without importing the producer SDK,
running the canonical Core schema or using a real grant. The qualified
launcher, installed Core environment and authenticated conversation host still
need receiving and native integration checks.

`CoreProcess` runs `core_bridge.py` with an explicitly configured, owned Python
3.14 interpreter and scratch environment. The bridge imports the actual Core
`validate_bytes`, not the weaker exported JSON schema. The Architect selected exact Core commit
`5b226fa9f2cf8d23337d5dee750828886675fb8b`; `core-validator-input.json`
records that immutable input and the host qualification obligations. It is not
a floating branch or an automatic substitution with release 0.26.0. The owned
installed environment and canonical consumer qualification are **not yet supplied**.
The host must verify exact source provenance and dependency closure before
binding the process; this declaration does not verify an environment by itself.
A missing Core package fails closed.
The scratch environment must include its owned `TMPDIR`. Validator stdout is
read with a byte cap and a five-second deadline; only the bridge's explicit
refusal marker together with its distinct exit code counts as a schema refusal.
Missing scripts, process failures and timeouts are unavailable, never successful
negative conformance cases.
Rasa runs separately on Python 3.11–3.12; do not combine incompatible environments.

No alternative schema validator is implemented. The consumer adds only its
binding, freshness and subset policy after Core accepts the original bytes:
`zeo.ui-result/v1`, exactly one card, no action references, a retrievable original,
and `complete:false` because the projection omits original result properties.
This consumer requires a source snapshot bound to the same invocation, observed
within 60 seconds; future, expired, missing or mismatched snapshots are refused.
The producer chooses the actual retained invocation reference; do not invent one.
Unknown, malformed or unsupported input is unavailable, never healthy-empty.

The renderer uses a fixed template and escapes every value. Evidence is inert
text, never a link or a fetch. All non-ASCII characters are displayed as literal
escapes, including invisible characters. This intentionally limited pilot loses
natural Unicode typography rather than duplicating Core's Unicode tables.
ASCII controls and DEL are also shown as literal escapes.
No returned HTML, CSS, JavaScript, SVG, commands or action references execute.
Payloads, validator diagnostics, provider data and credentials are not logged.

## Run the consumer tests

From this directory, using Python 3.11 or later:

```sh
python3 -m unittest discover -s tests -v
```

These tests inject an explicitly labelled fixture validation double to isolate
consumer behaviour. They **do not prove canonical schema validation**, a Mantle
import, training, model behaviour, provider access or live acceptance. Negative
byte/schema cases must also pass through the real qualified Core bridge before
integration. No fixture command accesses a provider or installs dependencies.

## Remaining acceptance

1. Qualify the approved Core dependency and producer mapping on exact source.
   Run byte-level rejection fixtures through Core, plus consumer tests.
2. Complete authenticated Mantle host/turn-container integration and normal full
   repository gates in the supported venue. The committed catalogue entry marks
   this pilot in progress; its lock uses exactly the sibling helpdesk example's
   registry package names and versions, not a fresh dependency upgrade.
3. Follow the Architect's owner-present sequence: council-cleared Broker flag
   read; normal pairing using its returned verification URL; owner creates the
   PoC application, grants one existing connection and assigns the device;
   ops' reviewed `devices_add` only if the flag is off.
4. Observe the actual metadata turn, validated card and next-turn replacement.
   Retain a redacted correlated trace. No guessed IDs, borrowed identity, early
   expiring pairing code, operation grant, deployment or provider spend.

Fixtures and source review do not complete these steps. The separate owned
article and newsletter work remains preserved; this directory covers only the
Rasa adapter/renderer slice.
