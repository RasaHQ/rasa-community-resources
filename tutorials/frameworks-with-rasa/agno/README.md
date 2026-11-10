# Keep an Agno adviser and its customer memory

Agno 3.1.2 native execution is qualified. The companion Mantle project
passes its decorated-tool controls, licensed validation/training and cold
archive loading. See `../agno-verification.json` for hashes and dated checks.

Willow Shop is fictional. Its public hand-cream record and preference are
synthetic. The native exercise retains a real Agno Agent, SQLite memory and
registered product tool. Scripted model responses let us inspect the actual
input before answering, rather than judge the wording of a generated reply.

The exercise holds the seeded preference and history configuration constant
while changing how an application supplies memory ownership:

- Stable customer ID with distinct conversation IDs.
- Conversation ID incorrectly used as the customer memory key.
- Omitted customer ID with a preference seeded under the fallback owner.

Both reused and fresh Agents are tested. All runs use new conversation IDs
after the initial conversation. Inspect both
preference presence and previous-question presence in the next model input.
The seed uses native database writes, not model-based memory extraction.
Automatic extraction and telemetry are disabled in this offline fixture.

## Selected environment

From the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/agno --owner willow-memory-demo
cd tutorials/frameworks-with-rasa/agno
make test
.venv/bin/python demo_memory_scopes.py
```

The printed rows are observations from the selected native SDK; they are not
an assessment of answer quality. Fifteen core controls and five actual Mantle binding controls pass
in the selected combined runtime. The standalone lock is checked separately.

After your jobs finish, preserve any needed database or output separately and
retire only this selected environment, from the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/agno --owner willow-memory-demo --inactive
```

References: [memory](https://docs.agno.com/memory/overview) and
[sessions](https://docs.agno.com/sessions/overview). These document separate
user and conversation scopes. An application must bind its user ID to an
appropriate trusted identity; a supplied ID by itself is not authentication.

Run `../agno/demo_handoff_owner.py` with the selected combined Python runtime
to inspect the one-argument ownership mutation. Both native runs return checked
public advice, while their initial memory inputs differ. Each starts with the
same seeded records and empty history in an independent database.
