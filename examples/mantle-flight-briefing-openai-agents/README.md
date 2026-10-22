# Brief me before I fly — work in progress

Author: Mator Clawson, rasa-bench
Assessed on: not_provided
Assessed by: not_provided — independent fresh-clone acceptance pending
Verified with: Python 3.12, the committed registry locks; complete demo qualification pending
Audience: Practitioners connecting Rasa Mantle to a managed specialist
Time: Allow time for the first dependency download

**Draft class head: the complete path is awaiting independent acceptance.**
From this checkout, create your private credential file and fill in your own values,
then install and start the demo:

```sh
cd examples/mantle-flight-briefing-openai-agents
make env
# Fill in your own values in .env with a text editor.
make setup
make run
```

For a new checkout after the class PR is merged:

```sh
git clone https://github.com/RasaHQ/rasa-community-resources.git
cd rasa-community-resources/examples/mantle-flight-briefing-openai-agents
make env
# Fill in your own values in .env with a text editor.
make setup
make run
```

Use a Git clone; ZIP downloads are unsupported because the credential tracking
and ignore checks require Git. Install Python 3.12 and `uv` first. The actual Mantle Inspector also requires
`RASA_LICENSE` (the free Developer Edition licence) in the example-root `.env` or your shell, including in scripted mode;
the launcher never bypasses the engine licence check. Model and voice keys are
optional for the scripted text path. Before class, [sign up for your own free
Developer Edition licence](https://rasa.com/rasa-pro-developer-edition-license-key-request)
and put the issued licence in the template’s `RASA_LICENSE` entry; submitting the
form alone does not make the runtime ready.

 Setup creates separate worker and Mantle
`.venv` environments from their committed locks. Both install `zeocore` from
PyPI; no private wheel, sibling checkout or editable source is used. Setup is
safe to repeat. A missing prerequisite stops with a sentence naming the fix.

## Open the actual Mantle inspector and the card page

Run starts the public-source briefing service and the actual `rasa inspect`
server. It trains the project first and keeps ownership of the processes.
Open **http://127.0.0.1:8942/** when the launcher reports ready: the combined
page shows the actual Inspector conversation beside the source cards. The
separate `/cards` and Inspector URLs are printed for diagnostics.
Press Ctrl-C in the launcher terminal to stop both
services and their children. If either port is occupied, the launcher refuses;
it does not stop another user's service.

With your Developer Edition licence and no model keys, the Inspector uses
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

Only the facilitator or participant supplies keys in the ignored example-root
`.env` or their shell. Never paste values into chat, committed files, URLs or logs. There is no
seat-operated live model or voice proof here. The selected model group remains
in `project/integrations.yml`; choose `openai` or `anthropic` there before a live
run with the matching environment key. A key for the other group alone does
not establish readiness.

Voice uses Deepgram Flux and Aura-2 through the maintained project integration.
Without `DEEPGRAM_API_KEY`, the launcher prints “Voice is off; set DEEPGRAM_API_KEY in your environment to enable it, or continue with text.”
Voice must not block the cards or scripted path. The owner-supplied Flux/Aura-2
configuration is merged only in the Inspector process, without writing keys.
If the voice-configured Inspector cannot start, the launcher stops its owned
process group and retries the actual Inspector once in text mode, leaving the
source service running. `--scripted` disables model
and voice credentials in its children. Actual voice failure fallback and spoken
weather scenario S13 require the operator's live check; no voice PASS is claimed.
The owner-maintained doctor prints only SET or MISSING for credential names.

The launcher reads only `RASA_LICENSE`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
and `DEEPGRAM_API_KEY` from this one `.env`; any other assignment is refused.
Use single-line `NAME=value` entries, optionally enclosing a value in matching
single or double quotes, with comments on separate lines. Values stay literal:
there is no variable expansion or shell evaluation. A shell variable takes
precedence only when that shell value is non-empty; an empty shell value uses
the file. The launcher passes values only to its child processes and leaves your shell unchanged. Git-tracked
`.env` files, files not ignored by Git, files larger than 4 KiB,
group/world-writable files, symlinks and runtime dotenv files in `project/` or
`worker/` are refused. Never commit `.env`; keep the empty `.env.example` as the shared template.
Implicit engine and uv dotenv loading stays disabled. Setup and offline tests
do not read participant credential values and strip shell credentials before
starting build tools or test processes.

Run `make help` for the ordered commands. `make env` copies the empty template
only if `.env` is absent, makes it private (mode 600), and prints the credential
names and sign-up links. `make doctor` checks readiness without printing values;
`make run-scripted` starts the labelled text fallback; `make test` runs offline
controls without participant keys. `make stop` contacts only this checkout’s
private control socket and lets its launcher stop both child process groups.
`make clean` removes only the local worker/project `.venv` directories marked by
this checkout’s successful setup. It preserves `.env`, caches, models, other
files and other checkouts; it refuses unmarked environments and a running demo.
The `./demo setup` and `./demo run` commands remain available underneath Make.

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

For a temporary tailnet viewer, set `BRIEFING_VIEWER_HOST` in the terminal to
this host's assigned address inside 100.64.0.0/10. Optionally set
`BRIEFING_VIEWER_NAME` to its `*.ts.net` name, then use `./demo run` (or pass
`--host` with that address). Open `http://YOUR_VIEWER_NAME:8942/` from the
allowed device. Without these options, launch stays on 127.0.0.1. Neither
service binds to a wildcard or public address. MCP still requires its runtime
authentication token.

**Tailnet access:** Inspector on port 5005 has no authentication of its own.
Any tailnet device that can reach it can drive the agent using the running
facilitator's model key and licence. Before enabling this viewer, restrict the
Tailscale ACL to the operator's device, or obtain the operator's explicit
acceptance of this temporary exposure. Then record that condition in the
terminal with `BRIEFING_VIEWER_ACCESS=operator-device-acl` or
`BRIEFING_VIEWER_ACCESS=operator-accepted`. This declaration does not configure
an ACL; the launcher refuses a tailnet start without it. The card display is shared with those
viewers, not private per browser. No keys belong in a URL or repository file.

When the route source provides no route, keep the live position facts and say
"Route not provided by the source". For weather and a computed arrival, provide
an explicit airport, for example `destination=LHR` or `destination=EGLL`, in the
same journey request. The airport is labelled "destination stated by traveller";
it is not a provider-reported destination. A conflicting source route is flagged.

The local ten-airport subset is from [OurAirports](https://github.com/davidmegginson/ourairports-data),
public domain under its Unlicense, pinned to source commit
`b529623d2a0b09a9be78d37fc7a7a5e1e16e3451`. Source URL and CSV SHA256 are
in `briefing/airports-ourairports-20261022.json`. Supported ICAO codes are CYYZ,
EDDF, EDDM, EGKK, EGLL, EHAM, KJFK, KLAX, LFPG and OMDB, plus their IATA codes.
Unknown codes are refused; there is no network lookup or guessed substitute.
