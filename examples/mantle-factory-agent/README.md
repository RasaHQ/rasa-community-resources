# Mantle factory agent

This is a Rasa Mantle agent that connects to a small, dark software factory (dark means no person reads each change; the locked tests decide). You ask for a change to the market card by typing in the Inspector. The agent's one tool, `run_factory`, sends your request to the factory. Locked acceptance tests that the builder never sees decide: ACCEPT or REJECT. A verdict is not a release. Nothing is deployed.

Here you run it in scripted mode, which needs no OpenAI key. A live coding builder is optional and comes after.

## What you need

- A Mac. The locked tests run inside macOS `sandbox-exec`. Without it the factory says NOT_READY and never claims ACCEPT.
- Python 3.12 and `uv`. Other Python versions are not supported.
- This example runs on Rasa Pro 3.21.0.dev5, the same as the travel example in `examples/`. Chapter 0 of the book runs on 3.21.0.
- For the live run only: your own OpenAI API key. Rasa Mantle has no model of its own, but in this example Mantle's choice of tool is scripted, so the key is used only by the coding builder.
- A free Rasa Developer Edition license. [Request it here](https://rasa.com/rasa-pro-developer-edition-license-key-request). The confirmation page is not the key, and the key reaches you after you submit.
- This repository cloned in full. The example uses the factory gate in `workshops/software-factories-masterclass/book/ready/ch06`, so it does not run from a copy of this folder alone.

## Scripted run (no OpenAI key)

Here teaching code chooses the tool. The factory judges one of two attempts that were written ahead of time. It does not write new code and it does not call a model. This is the reliable path.

```sh
cd examples/mantle-factory-agent   # from the root of your clone of this repository
./demo setup
export RASA_LICENSE='your own license'
./demo run
```

Open http://127.0.0.1:8947/ when it says it is ready. The first start trains the agent, which takes a little while. Ctrl-C closes everything. The run also ends by itself at the expiry time. If the default time has passed, give a future one: `./demo run --expires-at 2026-10-23T16:30:00Z`.

In the Inspector, type these two requests.

1. `Show at most three currencies on the market card`
   Expected: **ACCEPT**. The reply shows the verdict and a fingerprint, which identifies the attempt that was judged.
2. `Use the attempt that ignores the limit`
   Expected: **REJECT**, naming the failing test `test_b1_four_currencies_show_at_most_the_limit`. That attempt showed four currencies where the limit was three.

Any other request returns **NOT_READY**. That means no verdict was obtained, and it never means ACCEPT. The agent recognizes only these two requests.

To run the two real checks without the agent:

```sh
project/.venv/bin/python -m unittest discover -s . -p 'test_factory_gate.py' -v
```

## Live run (your OpenAI key, coding builder only)

In the live run, a coding builder on the OpenAI Agents API writes a new attempt for your first request. The locked tests judge it the same way as in the scripted run. Mantle's choice of tool stays scripted in both modes, so only the builder is live. Your second request, the one that ignores the limit, always judges the prepared bad attempt, so it still returns REJECT.

This needs your own OpenAI API key, and it costs money. The estimate is 15 to 150 US cents for one run. That is an estimate, not a cap and not the actual cost, so check your account budget first. One call can take up to 330 seconds.

1. Create the separate worker environment. It pins its own Python 3.12, zeocore 0.35.6 and openai 3.36.1, so it never changes the Mantle environment:

   ```sh
   ./demo setup-live
   ```

2. Create your own private file named `.env` in this folder with one line, `OPENAI_API_KEY=` followed by your key. It is ignored by Git. Never paste the key into a chat, a URL or a command, and never commit it. Keep the license in your shell as before.
3. Start the live run:

   ```sh
   ./demo run --builder-mode live --worker-python worker/.venv/bin/python \
     --env-file .env --evidence-root .runtime/factory-evidence
   ```

   Add `--expires-at` with a future time if the default has passed.
4. Type request 1. The reply shows the number of builder calls, the seconds, the verdict, the failing test if there is one, and a fingerprint that the tool computed from the attempt.

   One example, from a single run on 22 October with the `gpt-6-astra` builder: **ACCEPT**, 11 builder calls, about 67 seconds. Your numbers will differ, and one run does not promise the next. The cost notice appears before the call and again in the result. The actual cost is not measured.

The agent's tool reads the file you named and gives the key only to the builder's own process. The Inspector and the entry page never get it. Records of each run stay on your machine in `.runtime/factory-evidence`, and never in the model's results. The demo allows 12 funded live builder runs in total for that folder, not per day. A run that fails after it starts still uses one, and the REJECT request uses none.

NOT_READY means no usable verdict was obtained. It never means ACCEPT, and a live run is not promised to end in ACCEPT. If a live run does not complete, do not repeat it in a loop. Read the reply, then use the scripted run while you sort out your key or account access.

## Voice

Voice was not tested for this agent. In the travel demo, a test with recorded audio did not pass on the second turn, so type your requests.

## Troubleshooting

- **NOT_READY, "requires macOS sandbox-exec":** run on a Mac, or pair with someone who has one.
- **NOT_READY, "could not run to completion":** read the reason in the reply. In the scripted run you can type request 1 again. In the live run, another try can fund another build, so choose the scripted run first. If it repeats, a protected file may have changed: restore it from a fresh clone.
- **"Port in use":** the demo uses 8947, 5007 and 8948. Another program is using one of them. Stop it only if you know what it is, or wait until it is free.
- **"License missing":** export `RASA_LICENSE` in the same terminal where you run `./demo run`.
- **`./demo setup` fails:** check `python3 --version`. Use Python 3.12 only.
- **A refused public address:** the demo only binds to loopback unless a facilitator sets up a private preview.

## How the factory decides

1. You specify a change.
2. A builder produces an attempt. In the scripted run it is a prepared one.
3. Locked acceptance tests judge the attempt in a sandbox with no network. The conversational agent receives only the verdict record.
4. ACCEPT or REJECT. A verdict is not a release.

For an isolated local review while the class preview is running, choose distinct ports:

```sh
./demo run --entry-port 8960 --inspector-port 5020 --mcp-port 8961
```

Open http://127.0.0.1:8960/ for that run. Keep the same license and expiry requirements.
