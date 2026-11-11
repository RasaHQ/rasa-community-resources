# Shared banking domain

One dependency package for the two banking examples. This first slice implements
server-owned session/review state and adapter boundaries. It is **not yet an MCP
server, authenticated host adapter or vendor-contract mock**. No vendor code,
credentials or machine schemas are bundled here.

`banking_demo.BankingService` exposes `accounts`, `balance`, `review_transfer`,
`submit` and `status`. Only the future trusted host adapter may register a
`SessionContext` or invoke `confirm`, `cancel` and `reset`. These host methods must
never be registered as model-callable tools. Constructing the Python context is
not authentication; the native channel-to-MCP binding still needs qualification.

Reviews bind the current context and exact accounts, decimal amount and currency.
They expire, cannot survive reset/user switching, and are consumed before one
adapter submission. A lost response remains unknown; another call returns the
original outcome without retrying. Results distinguish accepted, queued and
posted. Other-account refusal does not query the adapter for existence.

The tests use an explicitly fictional **domain fixture**, not either vendor's
wire contract. They require no licence, model, speech key or network. Run from
this directory with Python 3.11 or later:

```sh
python -m unittest discover -s tests -v
```

Dependency-locked learner environments and browser/native-flow/MCP integration
belong to the consuming examples. These unit controls do not replace the required
devcontainer text-path CI, human Codespaces voice check, provider retention
settings, exact vendor-contract evidence or independent review.
