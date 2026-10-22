# A Mantle agent that requests a factory check

This example connects a real Rasa Mantle Inspector conversation to the workshop's protected acceptance gate. One skill, **Request a Change**, exposes one MCP tool, `run_factory(request)`.

Tool selection is **SCRIPTED**. The gate executes for real on one of two supplied, pre-written attempts. This example does not generate new code, call a model, apply an attempt, or release a product. It does not qualify voice.

Use macOS with `sandbox-exec`, Python 3.12, `uv`, and a free Rasa Developer Edition license. The locked Mantle version is Rasa Pro **3.21.0.dev5**, matching the travel example's runtime. The factory gate itself comes from `workshops/software-factories-masterclass/book/ready/ch06` in this checkout. Keep that folder: this example is not a standalone ZIP.

```sh
./demo setup
export RASA_LICENSE='your own license'
./demo run --expires-at 2026-10-22T16:30:00Z
```

Choose a future expiry when running on another day. On loopback, open `http://127.0.0.1:8947/`. The launcher owns only its own entry page (8947), Inspector (5007), and loopback MCP listener (8948). Ctrl-C or expiry closes all three. It refuses occupied ports, a missing license, and a public bind.

For an operator-approved tailnet preview:

```sh
./demo run --host YOUR_TAILNET_IP --viewer-name YOUR_MACHINE.ts.net \
  --viewer-access operator-accepted --allow-peer OPERATOR_TAILNET_IP \
  --expires-at 2026-10-22T16:30:00Z
```

The Inspector has no login; the explicit viewer-access flag confirms this access boundary. Only loopback, the bind address, and explicitly allowed peer addresses are admitted. Access metadata is written under ignored `.runtime/`. The MCP listener requires a fresh runtime-only bearer token and is bound to loopback. Provider keys are absent from all children. Optionally `--env-file` reads only `RASA_LICENSE` from an owner-supplied local file into child memory; it never copies that file.

In the actual Inspector, type these requests:

1. `Show at most three currencies on the market card` — judges `attempts/mine` against `tasks/b-limit-currencies.json`; expected **ACCEPT**.
2. `Use the attempt that ignores the limit` — judges `attempts/b-ignores-limit`; expected **REJECT**, naming `test_b1`.

Each reply includes the actual verdict, failing test, and gate fingerprint. Other requests return **NOT_READY** instead of inventing a build. No user-supplied path, command, or code is executed. A missing sandbox, changed protected file, or failed execution must remain **NOT_READY**, never ACCEPT.

The visible fingerprint identifies the judged input according to the adapter contract. It is not a deployment signature or proof that a product was released. The protected suite remains inside the gate; the conversational agent receives only its verdict record.

Run the adapter's two real cases with:

```sh
project/.venv/bin/python -m unittest discover -s . -p 'test_factory_gate.py' -v
```
