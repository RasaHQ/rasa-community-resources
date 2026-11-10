# A local decision model behind a Rasa account assistant

Use an open-weight Laya model to propose an account, then let Rasa ask the user
whether to use it. Python checks the confirmed proposal before reading its
fictional transactions. This deliberately extends the Jacaranda Bank tutorial
family; no real customer data or bank service is connected.

The implementation uses public packages and ordinary Mantle tools. Mantle's
existing orchestrator still decides when to invoke tools and writes the
conversation. This project adds a bounded account decision inside a tool
workflow; it does not patch or replace the Rasa engine.

## Start with reproducible offline controls

Use Python 3.12 and uv. From the repository root:

```sh
cd tutorials/jev-with-rasa/mantle
uv sync --prerelease=allow --locked
make demo
make demo-confirmation
make test
```

The demo passes scripted HTTP replies through the actual TypeSafe SDK. It shows
that response decoding, offered-choice membership and current eligibility are
separate checks. These are wire/application controls, not hosted Jev predictions.
The cold-archive control skips until you run licensed training.

`make demo-confirmation` replays a named account question, an unrelated user
request, another question and a later Yes. The earlier timestamp-only version
reads fictional account data: the Yes is later, but follows the other question.
The current next-user-turn check expires that proposal without reading. The
previous behaviour is reproduced by removing only the new check in memory.
SDK replies and dialogue events are controlled fixtures; this is an application
integration defect and fix, not a Rasa engine or model behaviour claim.

The conversation uses a proposal/confirmation path. A proposal reads no
transactions. A new user reply confirms or cancels it; the model supplies no
account ID or confirmation argument. The read checks the proposal token, its
conversation, owner and current account revision. A correction retires the old
proposal; a confirmed proposal is consumed once.

## Run the actual open-weight model

Create the separate model environment only if you want real local decisions.
Mantle's environment does not install Laya or PyTorch. In a first terminal:

```sh
cd tutorials/jev-with-rasa/local-laya
uv sync --locked
.venv/bin/python serve_local.py --cache-dir ./model-cache
```

This downloads one pinned English checkpoint, verifies the five artifact hashes,
and serves it on loopback port 5031 using two CPU threads. The model needs no
provider key. Keep one cache; do not copy it into other worktrees or environments.
See [the model setup](local-laya/README.md) for the exact runtime and weight pins.

In a second terminal, from `mantle`:

```sh
make demo-local
make worker-local
```

`demo-local` runs actual Laya proposals and exercises confirmation or cancellation
in the application. It is a standalone local-model exercise, not a recorded Rasa
conversation. `worker-local` keeps the account worker running on loopback 5029.
The public TypeSafe SDK talks to our narrow local Laya adapter; no TypeSafe key
is read or sent in this mode. Model and origin overrides are fixed in source.

## Add the Rasa conversation

In a third terminal in `mantle`, supply your issued Rasa licence and configured
writer-provider key as environment variables. `.env.example` lists their names;
these commands do not automatically load it.

```sh
make validate
make train
make run
```

The assistant listens on loopback port 5030. These are proposed user messages;
inspect the actual replies and tool results:

```sh
curl -s http://127.0.0.1:5030/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"local-model-demo-a","message":"Use demo 111111"}'
curl -s http://127.0.0.1:5030/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"local-model-demo-a","message":"Show my current account transactions"}'
curl -s http://127.0.0.1:5030/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"local-model-demo-a","message":"Yes"}'
```

The proposal tool sends the named-account question through `context.send`.
The confirmation tool checks the latest actual `UserUttered` event through the
public tool context, and requires a later user event than the one that created
the proposal. It handles a small explicit yes/no vocabulary. Extend and test that
vocabulary and the dialogue in the languages you intend to serve.

Confirmation must be the next user turn after the proposal. A later Yes after
another user turn expires the proposal and cancels its saved token. The user
must start a new account proposal. Delivery acknowledgement, time-based expiry
and durable atomic state remain production integration work. Restarting the
example loses its proposals.

Expiry removes the local proposal even if the worker cancellation request fails.
The tool reports proposal_expired in that case too. A lost cancel can leave the
worker's token pending until a new proposal for that conversation replaces it or
the worker restarts. The Rasa tool has discarded its local token and requires a
fresh proposal. A real service needs acknowledged, durable cancellation.

## Optional hosted Jev adapter

Stop `worker-local` with Ctrl-C before switching modes. `make worker` uses
scripted SDK replies. `make worker-live` uses the paid TypeSafe service and
requires `TYPESAFE_API_KEY`. Only that explicit mode sends hosted Jev requests.
It pins `jev-1.13.0`; local mode identifies the Laya checkpoint by its own revision,
not as Jev. Neither path uses an unqualified confidence cutoff to authorise reads.

The retained SDK client closes on worker shutdown. HTTP timeout is two seconds
and retries are disabled; this single-threaded development worker queues
requests, so the timeout is not a whole-conversation deadline. Each proposal
makes one decision request; confirmation uses the saved proposal without another
decision call. Mantle can make further model calls across the conversation.

Confidence and probabilities describe the selected backend's result. Preserve
its model identity and evaluate its scores on your own task; do not treat two
backends' raw confidence as interchangeable. Missing token usage remains null.
Keep measured runs and billing evidence private. This public project contains
the code, fictional fixtures, locks and setup needed to reproduce the tutorial.

## Application boundary and cleanup

`worker/jacaranda_jev/selector.py` checks the returned choice and distribution.
`proposals.py` holds each conversation's current proposal. `accounts.py` checks
current revision, offered membership and eligibility inside the read lock.
The one-step `select` method remains only for standalone decoder/eligibility
controls; the HTTP worker exposes the proposal, confirmation and cancellation
routes used by Mantle.

Public demo codes and REST sender labels do not authenticate a customer. All
three services are unauthenticated development examples containing only fictional
records; keep them on loopback. A real service needs authenticated channel
identity, an authorised data service and durable atomic state. Restarting a
process resets its in-memory fixture bindings and proposals.

Ctrl-C stops the foreground services. Retain source, manifests and locks; rebuild
only the environment you need. Exclude `.venv`, model caches, trained archives and
credentials from source copies. Retire completed experiment environments instead
of carrying them into another tutorial.
