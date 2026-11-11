# Shared banking domain

One dependency package for the two banking examples. Its conformance target is
our own shared banking contract `1.0.0`, declared in
[`banking_demo/contracts/banking-v1.json`](banking_demo/contracts/banking-v1.json).
The optional loopback MCP transport uses separate host and per-session
capabilities. It is not bank-customer authentication or vendor certification.
No vendor schema, derived vendor schema, credentials or real customer data is
bundled here.

Mocks follow the shared banking contract; vendor mappings are illustrative, based on public documentation, and not tested against vendor systems.

[`profiles/MAPPINGS.md`](banking_demo/profiles/MAPPINGS.md) identifies the public
operation descriptions followed by the two configurations and the unknown vendor
equivalents. Every result identifies the shared contract version, illustrative
profile and mock boundary. A real-vendor adapter is unavailable; no bank endpoint
is configurable and no sandbox account is required.

`banking_demo.BankingService` exposes `accounts`, `balance`, `history`,
`loan_payment`, `payoff`, `review_transfer`, `submit` and `status`.
Only the trusted host adapter may register a
`SessionContext` or invoke `confirm`, `cancel` and `reset`. These host methods must
never be registered as model-callable tools. Constructing the Python context is
not authentication; the native channel-to-MCP binding still needs qualification.

Reviews bind the current context and exact accounts, decimal amount and currency.
They expire, cannot survive reset/user switching, and are consumed before one
adapter submission. A lost response remains unknown; another call returns the
original outcome without retrying. Results distinguish accepted, queued and
posted. Other-account refusal does not query the adapter for existence.
An unknown outcome also blocks fresh reviews for that simulated principal,
including after logout/reset, so a new review ID cannot silently retry it.
There is no generic clear-unknown override. This state is in memory for the
teaching process lifetime, not a durable bank-operation journal or restart-safe
production guarantee; vendor reconciliation remains unimplemented.

The tests use an explicitly fictional **domain fixture**, not either vendor's
wire contract. They require no licence, model, speech key or network. Run from
this directory with Python 3.11 or later:

```sh
python -m unittest discover -s tests -p test_guard.py -v
```

For real MCP transport controls, install the `mcp` extra in the managed Python
3.12 environment, then run all tests. The SDK version matches the existing
confirmation-gate pattern. No bank, licence, model or speech keys are used.
Tests create their own private, ephemeral loopback capability and remove the
owned server process afterward.

`python -m banking_demo.server --profile jack-henry --port 8940` binds only
`127.0.0.1`; it requires an ephemeral `BANKING_HOST_CAPABILITY` supplied privately
by the launcher, never a committed value or browser/model input. Both profile
names select our shared-contract mock, not a real-vendor binding. The older
`--domain-fixture` flag remains a compatibility alias; no live-vendor mode is
enabled by omitting it. Private test construction with `domain_fixture=False`
still exercises an explicitly unavailable vendor path.

The fictional caller owns `checking-A`, `savings-A` and `loan-A` (or the `B`
counterparts). Balance defaults to `available`; `balance_type="ledger"` is also
supported. History defaults to page 1; page 2 gives the remaining fictional
entry. The next payment is supplied for `2026-01-20`. A payoff quote is supplied
only for `2026-01-15`; other dates return `unsupported`, never a calculated quote.
Loan-to-deposit transfers refuse. Deposit transfers above the supplied available
amount refuse; otherwise the Jack Henry illustration returns `queued` and the
Fiserv illustration `accepted`. Neither state claims posting or changes the
displayed balance. `--fault transfer-response-lost` explicitly simulates an
unknown dispatched outcome for refusal tests, without a provider request.

The host creates `HostClient(loopback_origin, host_capability)`, then calls
`open_session("demo-A")` (or `demo-B`). This issues an opaque per-conversation
MCP credential kept outside model arguments. `await host.call(session, tool,
arguments)` uses that credential in the transport header. Reset revokes it.
Only `host.confirm(session, review_id, exact_transfer)` can confirm a review;
it is a private control call, not an MCP tool. **The upstream host must prove
that this follows the real user's deterministic confirmation**, not a model's
boolean or invented conversation ID. The transport test uses a scripted host;
native flow/channel provenance is still unqualified. These identities are
explicit teaching simulators, never authentication of a bank customer.

The raw MCP boundary enforces our JSON input schemas before SDK coercion or
extra-field removal, including refusal of model-supplied `confirmed` or identity
fields. Tool discovery advertises those same versioned schemas. Results are
validated against our output schemas, with redacted unavailability for malformed
adapter values. Host proof and control endpoints are not tools.

Dependency-locked learner environments and browser/native-flow/MCP integration
belong to the consuming examples. These unit controls do not replace the required
devcontainer text-path CI, human Codespaces voice check, provider retention
settings, exact vendor-contract evidence or independent review.
