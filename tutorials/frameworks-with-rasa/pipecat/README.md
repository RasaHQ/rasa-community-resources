# Keep Pipecat speech and give Rasa committed turns

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native interruption, composition and loopback HTTP controls
**Verified with:** pipecat-ai 1.12.0, Rasa Pro 3.21.0.dev5 and Python 3.12.13.
Seventeen native Pipecat/REST controls and five decorated Mantle controls pass.
Project validation, licensed training and cold archive loading pass separately;
see `../pipecat-verification.json` for source and dated evidence hashes.

This Juniper Mobile example retains an existing Pipecat transport, STT, TTS and
turn-aggregation pair. A native `RasaDialogueProcessor` replaces the dialogue
stage and calls the separately configured Rasa REST channel. The adapter sends
only the latest committed user text. Existing speech services stay in Pipecat.

The public synthetic conversation asks for north or central, then explains a
public maintenance record. The supplied Mantle tool reads those fixed records.
Account operations require their own implementation and authorization.

## First reproduce the late-response control

Use Python 3.12, from the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/pipecat --owner juniper-pipeline-demo
cd tutorials/frameworks-with-rasa/pipecat
make test
make demo
```

`demo_interruption.py` runs an actual native PipelineWorker and WorkerRunner.
A committed context starts a controlled dialogue request. A real
InterruptionFrame reaches the sink, then that request completes. With the
response-generation check present, old text is discarded. Removing only that
comparison from the actual ownership method emits the old text after the same
native interruption. The two JSON records retain both results.

These controls use scripted dialogue replies and an inspectable text sink.
The loopback HTTP controls exercise the actual REST client. Assess microphone,
speech-provider, playback and acoustic interruption behaviour with your own
retained services and recordings.

The processor keeps accepted requests in order. New speech ownership does not
undo a Rasa request already accepted by the server. A queued superseded request
is skipped before dispatch; an accepted request may complete before the current
one starts. The REST client's ten-second timeout bounds that HTTP request, not
all server-side work. Keep side effects behind their own application checks.

Speculative LLMContextFrame inputs are skipped before dialogue dispatch.
The default supplied aggregation pair sets `empty_user_turn=None`: empty-turn
recovery belongs to your interface. A retained custom pair can keep its own
settings, but the adapter accepts only a final user message. A developer recovery
prompt alone cannot create another Rasa request; show repeat/retry state in your
interface when a caller interrupts without a usable transcript. Context
frames ending in an assistant message, empty text, oversized text or multimodal
content are rejected by this text adapter. A request failure produces a generic
native ErrorFrame, with its raw exception withheld; use the existing worker's
`on_pipeline_error` handler to show waiting/retry state in the interface.

## Start the public Rasa conversation

Rasa has a separate lock and process. If you already have a suitable Rasa REST
endpoint, retain it instead of creating another server/environment. For this
supplied public example, create only its selected environment:

```sh
# From the repository root:
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/pipecat-mantle --owner juniper-dialogue-demo
cd tutorials/frameworks-with-rasa/pipecat-mantle
make test
make validate
```

Export `RASA_PRO_LICENSE` and `OPENAI_API_KEY` using that project's blank
`.env.example` as the variable list. Then `make train` and `make run`. The server
binds to localhost port 5020 with a text REST channel. In another terminal,
from the Pipecat project:

```sh
.venv/bin/python run_text_demo.py --message 'Is maintenance planned for north?'
.venv/bin/python run_text_demo.py --message 'And for central?'
```

The same configured sender retains the Rasa conversation. Inspect the returned
wording against public references JM-N-101 and JM-C-102, and check the missing
area/retry flow. This reader-run command invokes your configured model. Native
controls and licensed archive qualification are separate from that assessment.

The `public-juniper-demo` sender is a public fixture, freely configurable by the
local caller. For private records, resolve a connection's customer principal
through the channel's authentication/authorization before selecting the Rasa
sender. A frame's user text never chooses this client's sender argument.

## Insert it into the voice bot you already own

Keep your existing component construction, provider keys and transport hooks.
The selected core lock qualifies the text adapter. Retain the provider extras
and versions in your existing voice bot's lock when adding these source files;
qualify that combined bot against the pinned Pipecat release and your speech services.
In the bot's asynchronous setup, use the supplied composition function:

```python
from aiohttp import ClientSession
from pipecat.pipeline.worker import PipelineWorker
from pipecat.workers.runner import WorkerRunner
from rasa_dialogue.client import RasaRestClient
from rasa_dialogue.compose import with_rasa

# transport, stt, tts and context_aggregator come from your existing bot.
async with ClientSession() as session:
    ask = RasaRestClient(
        session, "http://127.0.0.1:5020/webhooks/rest/webhook", "public-juniper-demo"
    )
    pipeline = with_rasa(
        transport, stt, tts, ask, aggregator=context_aggregator
    )
    worker = PipelineWorker(pipeline)
    # Retain your transport connect/disconnect event handlers for this worker.
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()
```

`compose.py` retains those media objects once in the native pipeline. It places
the Rasa dialogue stage between the user aggregator and the existing TTS path.
Rasa REST replies are buffered until that HTTP response completes. Multiple text
records are joined with line breaks in one native text frame; this adapter
provides complete-message output. Assess time to first speech with your actual
model and speech services when accepting the voice path.

The adapter consumes committed context, emits native response-start/text/end
frames, and forwards control frames. Keep one TTS path and the existing audio
interruption handling. The generation check addresses responses that arrive
later; playback acceptance needs actual audio evidence.

## Retire the completed experiment

Stop your own bot/server and finish or cancel its outstanding requests. Keep
needed recordings, state and outputs separately. From the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/pipecat --owner juniper-pipeline-demo --inactive
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/pipecat-mantle --owner juniper-dialogue-demo --inactive
```

Retire only environments you created, with their actual owner names. Source and
locks remain. The [pipeline documentation](https://docs.pipecat.ai/pipecat/learn/pipeline)
and [interruption guide](https://docs.pipecat.ai/pipecat/fundamentals/interruptions)
describe the native frame paths; this example pins pipecat-ai 1.12.0.
