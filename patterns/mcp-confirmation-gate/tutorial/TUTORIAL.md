# Test tool confirmation in a Rasa agent that uses MCP

Teaching manuscript accompanying this maintained pattern. Website publication
and independent rendered review are separate release steps.

If your support agent reads cases through an MCP server, it receives more than
case data. The server also supplies tool descriptions, which the model sees
when deciding what to call. You need to check what happens if the model asks
for an action the customer has not requested.

The Model Context Protocol (MCP) lets an agent use tools supplied by another
service. Here, that service reads a fictional support case on your own machine.

In this exercise, you will run the same fictional support agent with and
without a confirmation requirement. You will inspect whether its recording
tool runs immediately or waits for a later confirmation. You will also check
what happens when confirmation is cancelled or sent too soon.

The model responses are scripted. This makes the tool requests repeatable,
so you can test the engine's behaviour without paying for model calls. It does
not test whether a model follows an injected instruction or understands consent.

## What you will run

The local MCP server has one case-reading tool. Its description names a
recording operation, and its result contains a fictional value. A separate
script supplies the model response that requests that operation.

Mantle loads the skill, receives the MCP result and handles the requested tool
call. The recording tool returns `simulated_recording`; it creates no file or
customer record. All services in the exercise listen on your own machine.

The two variants use the same skill and tools. Only this setting changes:

```yaml
tool_constraints:
  - record_local_canary:
      requires_confirmation:
        enabled: true
```

In the second variant, `enabled` is `false`. Keeping that difference small lets
you identify what the confirmation requirement changes.

## Before you start

You need Python 3.12, uv and a checkout containing this pattern. Run the
commands below from `patterns/mcp-confirmation-gate` in that checkout. The lock
pins Rasa Pro 3.21.0.dev5 and MCP 1.28.1. The recorded installation and CLI
checks used macOS on Arm64; they do not establish the same result on other
platforms or releases.

The automated checks use a fake model key and make no model-provider requests.
The optional `rasa train` and `rasa run` exercise in the README needs a valid
Rasa Pro licence. Keep your licence in your shell, out of source files and
shared logs.

Install the locked dependencies into this project's environment:

```bash
uv sync --prerelease=allow --locked
```

Check the interpreter and installed pins before continuing:

```bash
uv run --locked python -c 'import sys; from importlib.metadata import version; print(sys.version_info[:2]); print(version("rasa-pro")); print(version("mcp"))'
```

The three lines should be `(3, 12)`, `3.21.0.dev5` and `1.28.1`. A different
result means you are not running the environment this exercise qualifies.

If installation fails, check that uv selected Python 3.12 and retain the error.
Do not change the package pins to get past it: that would be a different
exercise. Use one environment for both variants; their source configurations
are prepared separately.

## Run the paired conversation check

Run this command from the same project directory:

```bash
RASA_TELEMETRY_ENABLED=false PYTHON_DOTENV_DISABLED=true \
  OPENAI_API_KEY=placeholder-not-a-real-key \
  uv run --locked python -m unittest test_turn_loop -v
```

The check packages both agents, loads each archive and sends a message through
Mantle's actual turn loop. It starts and stops its own loopback MCP server.
The model completion boundary supplies the fixed requests; the tracker,
confirmation gate and tool invoker remain real.

Success ends with `OK`. That means the following assertions passed, rather
than that a particular sentence sounded convincing:

| Point in the conversation | Confirmation enabled | Confirmation disabled |
| --- | --- | --- |
| Script requests the recording after reading the case | Tool result is `awaiting_confirmation` | Tool result is `simulated_recording` |
| A later user turn arrives and the script supplies boolean confirmation | Stored value is simulated once | No second turn is needed for the first simulation |

The scripted first message asks to read a case. It does not ask to record the
value. The gated result therefore shows a requested call waiting instead of
executing. The ungated result provides the comparison: the same request
executes immediately.

If the check fails, read the first traceback and the assertion it names.
The script checks the exact fixture description and fictional value. A failure
there may mean the data did not arrive, or that you changed the fixture text;
compare it with `mock_server.py` before diagnosing a transport problem.
A different tool status means the engine did not follow the behaviour
this exercise asserts. Preserve the failure; do not treat it as a passing
result because the assistant printed a confirmation question.

## Check the cases a happy-path conversation misses

A later positive confirmation is only one case. Run the native gate controls:

```bash
RASA_TELEMETRY_ENABLED=false PYTHON_DOTENV_DISABLED=true \
  OPENAI_API_KEY=placeholder-not-a-real-key \
  uv run --locked python -m unittest test_native_confirmation -v
```

These six checks use the installed gate and invoker with an in-memory tracker
stand-in. They supply arguments directly, so they check engine rules rather
than a model's interpretation of a customer's answer.

| Change to the pending call | Expected result |
| --- | --- |
| Confirm in the same user turn | The tool does not execute |
| Confirm in a later turn, with a replacement value alongside the flag | The originally stored value executes once |
| Confirm again after that execution | The tool does not execute a second time |
| Supply boolean `false` in a later turn | The pending call is cancelled without execution |
| Supply the string `"yes"` instead of a boolean | The tool remains pending |
| Request the pending tool again with different arguments | Its stored arguments remain unchanged |

The ungated invoker is also checked for immediate execution. The command ends
with `OK` only if all six tests pass; several assertions belong to the same
test.

## Repeat it through the text HTTP channel

Once the turn-loop check passes, add the REST channel to the exercise:

```bash
RASA_TELEMETRY_ENABLED=false PYTHON_DOTENV_DISABLED=true \
  OPENAI_API_KEY=placeholder-not-a-real-key \
  uv run --locked python -m unittest test_http_turn_loop -v
```

This sends real HTTP requests to Rasa's REST handler on an automatically
chosen loopback port. It checks response status, recipient identifiers and
the same stored tool results. It closes its client and server afterwards.

This in-process test disables Sanic's source-rewriting optimisation because it
cannot transform Rasa's wrapped send method. For the separate, licensed CLI
exercise, follow the README's setup, training and local model-service commands.
That route was also checked with `rasa run`; it does not use the in-process
server adjustment.

## Use the result in your own application

Put the confirmation requirement on the tool whose execution needs approval.
Test that tool with the actual arguments your application stores. Include
cancellation, repeated requests and changed values, as well as a positive
confirmation. A spoken acknowledgement or written question is not evidence
that the operation waited; inspect the tool result and any real backend effect.

This exercise supplies a boolean confirmation through a script. Before using a
real model, separately test how it interprets ambiguous answers, refusals and
changes to the requested action. Your backend still needs its own checks for
who may act, on which record and with which values. A confirmation gate does
not supply those permissions.

The description/result arrangement is inspired by
[research into trust in tool-calling pipelines](https://arxiv.org/abs/2609.18217).
This exercise does not reproduce its attacks, compare detectors or measure
model susceptibility. It gives you a repeatable way to check what the engine
does after a tool request has already been made.

## Check your understanding

Suppose the model writes “Would you like me to save this?” but the tracker
already contains `simulated_recording`. Has confirmation been enforced?

No. The simulated operation has already run. In this exercise, the first
gated call must instead return `awaiting_confirmation`; the later execution
must use the stored value. Check the recorded tool result, not only the text.

For the recorded source hashes, archive checks and CLI cleanup results, see
the qualification JSON files under `qualification-history/`. They describe the
tested release and platform; they are not a claim of production safety.
