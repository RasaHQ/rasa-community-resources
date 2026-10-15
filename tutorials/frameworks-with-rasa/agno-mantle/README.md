# Add return checks to an Agno and Rasa shopping assistant

Willow Shop's existing native Agno adviser keeps its registered product tool,
model and SQLite customer memory. Mantle exposes the read-only public product
task. Application code maps the channel sender to a stable demo customer and a
distinct conversation. Product advice takes a question; the new return check
takes an order reference.

**Author:** Rod Rivera
**Assessed on:** 2026-10-15
**Assessed by:** OpenAI client-contract controls assessed on 15 October 2026 and written-policy checks; refund-native/build evidence is recorded separately.
**Verified with:** Standard-library policy checks; SDK steps are locked to Rasa Pro 3.21.0.dev5 and Agno 3.1.2.

## Check a return against the shop's written policy

The existing adviser still answers product questions. The additional refund
skill looks up invented order and inspection records for the same public demo
customer. It makes a read-only offer from the recorded amount paid. It cannot
issue a payment or contact staff.

Read [the fictional policy](REFUND-POLICY.md) first. It states which returns
qualify for an automatic full-refund offer and which need an inspection or
staff review. You will test those rules with invented order records before
connecting the check to a conversation.

You can check the pure policy without an SDK, licence or provider key. From
the repository root:

```sh
PYTHONPATH=tutorials/frameworks-with-rasa/agno python3 -B -m unittest discover -s tutorials/frameworks-with-rasa/agno-mantle/tests -p test_refund_policy.py -v
```

A passing result checks the written rules and order ownership in the fixture.
It does not show that a model calls the tool or accurately explains its result.
After installing the selected runtime below, `make test` also exercises the
actual Mantle invoker with fixed channel contexts. The binding takes an order
reference; customer identity comes from the existing public demo mapping,
while payment and inspection values come from the order lookup.

Try `WS-RETURN-01`, `WS-RETURN-LATE` and `WS-RETURN-PENDING` with sender
`willow-a-chat`. Their records represent an automatic offer, staff review and
a missing inspection. `willow-b-chat` cannot read those fixture orders through
the tool. Anyone can choose a public demo sender name, so this is not a login
or a production access-control implementation. Replace that mapping with an
authenticated channel identity before using real records.

Staff review is a status, not an acknowledged handoff. The tool does not change
a payment, open a ticket or send customer details anywhere. Check those
integrations separately if you add them.

## Start only the selected runtime

Use the committed lock for this combined project; do not upgrade its OpenAI
SDK independently. The lock includes the native adviser. The combined demo
needs only this environment; the standalone Agno environment is optional when
running that project separately.

From the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/agno-mantle --owner willow-conversation-demo
cd tutorials/frameworks-with-rasa/agno-mantle
make test
make validate
```

The controls use scripted replies from the real Agno executor. They inspect
the actual model input, native product tool result, structured output and
decorated Mantle binding. Customer preferences are seeded through native
database writes. Automatic memory extraction is disabled in this exercise.

## Check OpenAI client compatibility without a provider key

The shared adviser allows OpenAI SDK `>=2.44.0,<2.55.0` so each combined
runtime can satisfy Rasa's own SDK requirement. The committed standalone and
Mantle locks still select `2.44.0`; the maintained Rasa pin is unchanged.
Use the committed locks rather than upgrading the SDK independently.

The selected 15 adviser controls and eight Mantle/client controls passed on
15 October 2026 with Rasa `3.21.0.dev5` / OpenAI `2.44.0`, and in an isolated
candidate with Rasa `3.21.0.dev10` / OpenAI `2.54.0`. Agno remains `3.1.2`.
This checks those two installed combinations, not every intervening SDK release.
The candidate is not the catalog's tested release pin.

The three checks in `tests/test_openai_client_contract.py` use Agno's real
OpenAI client with an in-memory HTTP transport. They check the product-tool
round trip, structured reply, provider-error handling and refusal of an unknown
demo sender before any client request. Their responses and usage counts are
explicit fixtures, not generated answers or cost measurements. No provider
key, network connection or model inference is needed. Run them with the
selected environment above:

```sh
.venv/bin/python -m unittest discover -s tests -p test_openai_client_contract.py -v
```

For a live conversation, export your own `RASA_PRO_LICENSE` and
`OPENAI_API_KEY` using `.env.example` as the variable list. `SHOP_MODEL`
selects the adviser's model. Mantle's model is configured separately in
`integrations.yml`; each model makes its own provider requests.

```sh
make train
make run
```

In another terminal, compare the three public demo senders:

```sh
curl -sS http://localhost:5020/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"willow-a-chat","message":"Tell me about the hand cream."}'
curl -sS http://localhost:5020/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"willow-a-voice","message":"Tell me about the hand cream."}'
curl -sS http://localhost:5020/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"willow-b-chat","message":"Tell me about the hand cream."}'
```

The second sender exercises another conversation for the same public customer.
Its name identifies a simulated channel; this REST example supplies text.
Check product `WS-HAND-01`, the generated explanation and the native memory
observations. The controls inspect supplied context; assess your own model's
wording and use of preferences when running the live exercise.

## Keep customer memory separate from conversation history

The application creates a fresh native Agent per request while preserving
SQLite storage under `.state/public-shop.sqlite`. A stable user key allows the
same customer's preferences to survive a new conversation. A thread key
separates chat history. Recreating the Agent changes neither storage scope.

The service serializes native requests with a thread lock. If an async caller
is cancelled, the thread can continue; it holds that lock until its operation
ends. The model client has a ten-second per-request timeout and zero SDK
retries. These settings are separate from an overall operation deadline.

The public sender registry and seeded preferences are synthetic. Anyone using
this demo's REST endpoint can supply a demo sender name. For real customer
data, replace the registry with a channel principal established after your
authentication and authorization checks. Preserve that principal when
mapping a new conversation to its existing memory. The native ID fields label
storage scopes; your application owns access control.

The task returns advice for one public product. It places no order, makes no
payment and performs no profile update. The fixed schema checks the product
ID and output shape; assess explanation quality separately.

After stopping your own server and completing native operations, preserve any
database you need and retire the selected environment from the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/agno-mantle --owner willow-conversation-demo --inactive
```

Environment retirement retains the database, source and lock. Review stored
data separately; an ignored database is not disposable by default.

Run `../agno/demo_handoff_owner.py` with the selected combined Python runtime
to inspect the one-argument ownership mutation. Both native runs return checked
public advice, while their initial memory inputs differ. Each starts with the
same seeded records and empty history in an independent database.

## Earlier product-advice qualification

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native memory-owner controls, decorated Mantle bindings and licensed build qualification
**Verified with:** Rasa Pro 3.21.0.dev5, Agno 3.1.2 and Python 3.12.13. The
original 20 native controls and project validation passed on that date. Licensed training and cold archive
loading were qualified at `fe5aeb26`; later changes add fixture observations and
a one-argument mutation control. Those historical hashes are retained in
`../agno-verification.json`; they do not qualify the refund extension.

Further reading: [an independent study of model refund decisions](https://github.com/KarenSpinner/shopping_agents/tree/5905a95f0195c686c04d2fb5ba1684973cd194d4) explores how company instructions affect discretionary offers. This project uses its own fictional policy and records; it does not repeat or measure that study.
