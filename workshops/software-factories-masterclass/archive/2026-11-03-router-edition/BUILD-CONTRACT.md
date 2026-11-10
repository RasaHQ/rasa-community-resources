# What the router workshop must do: build contract

This page says what each part of the workshop promises and what it does not. It describes the router restart helper and the factory around it, as built in a GitHub Codespace on Rasa Mantle. It is a contract for the workshop material. It makes no claim about a real router or a production system.

## The user journey

1. You open a codespace and build the router helper in about 30 minutes.
2. You ask for a restart. The helper asks you to confirm, and records one command, `REBOOT`, after you say yes.
3. You say "reset it". The helper asks whether you mean a restart or a factory reset, and sends nothing until you answer.
4. You ask for a factory reset. The helper says it cannot do that here and offers a person. It records nothing.
5. You run a source-file check on the helper's tool file. It passes while the file says `REBOOT`, and fails when you change it to `FACTORY_RESET`. You change it back and it passes again before you retrain.
6. You run a builder, put it behind the helper, and ask for a new read-only operation. A saved file comes back with its absolute path and sha256.
7. You run a gate on that file and on four fixed candidates. You record whether you approve or refuse the change.

## What each part promises

| Part | It promises | It does not promise |
|---|---|---|
| Router helper (Mantle skill and tool) | A confirmation before the command, `REBOOT` only after a yes, a clarifying question for "reset", a refusal with an offer of a person for a factory reset | That it never says anything else. After a first message or a restart the engine can add its normal follow-up question. It contacts no router. |
| Source-file check | Reads the configured command in the tool file and fails if it is not `REBOOT`. Exits 2 when it finds no command | That the helper ran that command in a live conversation. It is separate from the conversation checks |
| Builder (OpenAI Agents API) | Writes and saves one file, `check_line_status.py`, and reports its path and sha256. The default practice builder uses a public sample, is labeled a fixture build, and starts no Agents session. One optional live build uses your own key and is billed | That a finished session is acceptable, or that cost was measured |
| Tool server and skill | Hand your request to the builder and show the build id, saved flag, path and sha256, ending "Nothing was applied to the helper" | Anything applied to the helper. Read terminal 2 before asking again if the reply says it cannot tell whether a build started |
| Gate | Judges the saved file's bytes without running it. Accepts only one function, `check_line_status()`, returning plain values. `good.py` is `ACCEPT`; the three `bad_` files are `REJECT` | A general sandbox, or proof of all future behavior |
| You, at the last gate | Record approve or refuse, and why | That anything is installed or applied. The record is for manual review |

## Receipts to keep

- The helper's reply for each of the four rows.
- The source-file check output for `REBOOT`, `FACTORY_RESET` and restored `REBOOT`.
- The builder's build id, absolute path and sha256, with the mode (fixture or live).
- The gate's verdict for your file and the four candidates.
- Your written decision.

## Not part of this workshop

Voice, a travel assistant, a local setup on your own machine, and any release into a running system. The presenter may show a Studio 2 preview. You cannot try it yet and need it for nothing here.
