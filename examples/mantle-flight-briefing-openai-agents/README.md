# Brief me before I fly — work in progress

Author: Mator Clawson, rasa-bench
Assessed on: not_provided
Assessed by: not_provided — independent fresh-clone acceptance pending
Verified with: Python 3.12, the committed registry locks; complete demo qualification pending
Audience: Practitioners connecting Rasa Mantle to a managed specialist
Time: Allow time for the first dependency download

**Draft class head: the complete path is awaiting independent acceptance.**
From this checkout, the two commands are:

```sh
cd examples/mantle-flight-briefing-openai-agents
./demo setup
./demo run
```

For a new checkout after the class PR is merged:

```sh
git clone https://github.com/RasaHQ/rasa-community-resources.git
cd rasa-community-resources/examples/mantle-flight-briefing-openai-agents
./demo setup
./demo run
```

Install Python 3.12 and `uv` first. The actual Mantle Inspector also requires
`RASA_LICENSE` (the free Developer Edition licence) in your own terminal
environment, including in scripted mode;
the launcher never bypasses the engine licence check. Model and voice keys are
optional for the scripted text path. See the repository's developer-licence
instructions if you do not have a Rasa Pro licence.

 Setup creates separate worker and Mantle
`.venv` environments from their committed locks. Both install `zeocore` from
PyPI; no private wheel, sibling checkout or editable source is used. Setup is
safe to repeat. A missing prerequisite stops with a sentence naming the fix.

## Open the actual Mantle inspector and the card page

Run starts the public-source briefing service and the actual `rasa inspect`
server. It trains the project first, prints both loopback URLs when ready, and
keeps ownership of the processes. Open the printed inspector URL to chat and
the card-page URL beside it. Press Ctrl-C in the launcher terminal to stop both
services and their children. If either port is occupied, the launcher refuses;
it does not stop another user's service.

With a Rasa Pro licence and no model keys, the Inspector uses
**SCRIPTED tool selection**. The pinned
engine, skill execution, MCP requests, hooks and browser Inspector are real;
the selection of tools is deterministic and is not model reasoning. This is
separate from `scripted_demo.py`, the historical console-only replay harness.

For an explicitly keyless run even when your shell has model keys:

```sh
./demo run --scripted
```

In the Inspector, supply your own explicit journey, using this syntax:

```text
callsign=TEST123 meeting=2026-10-22T21:00:00Z transfer=45
```

`TEST123` illustrates the syntax, not a promised airborne flight. Replace it
with a real callsign. The meeting includes its date and timezone. Transfer is
an assumption in minutes, never a traffic observation. A follow-up such as
`transfer=60` revises the same briefing. Missing or invalid inputs are asked
for; the launcher does not guess a journey.

The four cards are flight position with a computed arrival estimate, hourly
weather, the arrival/transfer/meeting timeline, and a currency watchlist. Market
values are daily reference rates, not live stock quotes. Source outages and
missing observations show unavailable reasons rather than invented values.
See [source choices and attribution](SOURCE-CHOICES.md). Values come from source
handlers, never from model prose. The card page uses Core's renderer, inline
styles and SVG; it loads no remote browser assets.

## Optional live model and voice

Only the facilitator or participant supplies keys, in their own terminal
environment. Do not paste values into chat, files, URLs or logs. There is no
seat-operated live model or voice proof here. The selected model group remains
in `project/integrations.yml`; choose `openai` or `anthropic` there before a live
run with the matching environment key. A key for the other group alone does
not establish readiness.

Voice uses Deepgram Flux and Aura-2 through the maintained project integration.
Without `DEEPGRAM_API_KEY`, the launcher prints “Voice is off; continue in text.”
Voice must not block the cards or scripted path. The owner-supplied Flux/Aura-2
configuration is merged only in the Inspector process, without writing keys.
If the voice-configured Inspector cannot start, the launcher stops its owned
process group and retries the actual Inspector once in text mode, leaving the
source service running. `--scripted` disables model
and voice credentials in its children. Actual voice failure fallback and spoken
weather scenario S13 require the operator's live check; no voice PASS is claimed.
The owner-maintained doctor prints only SET or MISSING for credential names.

## Provenance, access and remaining checks

The service runs with a private, fresh `BRIEFING_MCP_TOKEN` passed only to its
children. A private briefing ID permits get/revise access. Possession is not
engine-sender isolation; never share or log that ID. Existing hooks protect its
presentation. No listing or enumeration tool is provided.

This launcher does not implement an alternate inspector, a provider API, a
credential store or a card renderer. Its scripted provider is installed only
in the child process at the pinned engine's LLM-client factory. No installed
engine file is edited. Unsupported engine or Core releases fail startup rather
than opening a replacement chat page.

The source-adapter/renderer release pin, owner engine/voice configuration,
independent clean-clone run, four-card screenshots, second-act checkpoint and
operator live check remain receiving gates. A passing launcher unit test is
not browser or class acceptance. The factory second act and completed market
card checkpoint must be demonstrated before the class is accepted; the
launcher does not relabel an old console transcript as that demonstration.

Historical paths remain described in [the project instructions](project/README.md)
and [the separate managed model worker](LIVE-WORKER.md). Their older wheel and
two-shell instructions are not this class launcher's setup path.

Teaching code uses the repository [license](../../LICENSE). Rasa Pro has its own
terms; any licence requirement is an explicit prerequisite, not a skipped check.
