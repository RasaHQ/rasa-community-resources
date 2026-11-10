# Keep LiveKit rooms and speech; let Rasa handle dialogue

**Author:** Rod Rivera
**Assessed on:** 2026-10-11
**Assessed by:** Native stream, RoomIO, composition and loopback HTTP controls
**Verified with:** livekit-agents 1.8.6 and Python 3.12.13.
Twenty-one native stream, RoomIO, composition and loopback HTTP controls pass;
source and dated qualification hashes are recorded in `../livekit-verification.json`.
The existing public Rasa maintenance project is separately qualified in
`../pipecat-verification.json`; reuse it instead of copying another application.

Keep your existing LiveKit room, speech services, turn detector and transport
setup. The supplied native LLM implementation forwards the latest plain-text
user message to your Rasa REST conversation and returns a native ChatChunk for
the existing speech path. Domain tools stay in Rasa.

Juniper Mobile is fictional. Its read-only task explains the synthetic north
and central maintenance records JM-N-101 and JM-C-102. Participant identities
in this example label public state. Resolve authenticated customer identity
and account access in your application before connecting private records.

## Reproduce the native text boundaries

Use Python 3.12 from the repository root:

```sh
python3 scripts/workspace.py start tutorials/frameworks-with-rasa/livekit --owner juniper-room-demo
cd tutorials/frameworks-with-rasa/livekit
make test
make demo
```

The actual LiveKit LLMStream controls collect scripted replies. A synthetic
server-state boundary records each sender and its earlier messages. Keeping
both room and participant in the sender derivation separates two rooms that
reuse the same public participant name. Omitting the room preserves valid
stream output while reusing the first room's synthetic history. Recreating the
native model object with the same correct binding retains that conversation.

A separate actual RoomIO control holds `reader.read_all()` pending. Native
participant filtering accepts that reader while A is linked; native disconnect
and participant-link handling then change the connection before reading ends.
A bare callback can deliver that old text to the session boundary. The supplied
callback checks the current participant connection at completion, and again
after awaiting interruption. It rejects the old text, including reconnect with
the same participant identity. A positive current-connection control verifies
that usable text still reaches the session boundary.

These are native SDK tests with synthetic room participants, text readers,
session-output and server-state boundaries. They exercise the real stream and
RoomIO handlers, not a connected WebRTC room or acoustic recording. Accept the
actual microphone, provider services, transport and playback configuration in
your existing bot separately. The adapter buffers complete REST output; assess
time to first speech with your chosen dialogue model and speech services.

Generic model retries are disabled for this adapter. A failed REST turn may
already have changed the Rasa conversation; native retry settings must not
silently resubmit it. Failure returns a generic native APIError rather than
invented answer text. Use your existing session error/recovery handling. Local
stream cancellation cancels the pending local request; server acceptance and
remote work have their own lifecycle.

The native stream supplies no token usage. Capture actual model usage on the
Rasa side; do not interpret absent or default LiveKit usage fields as free
inference. No provider/model request is used by the scripted native controls.

## Reuse the existing public Rasa project

Use your own suitable Rasa REST endpoint, or follow
[`../pipecat-mantle/README.md`](../pipecat-mantle/README.md). That selected project
has its own lock, licence and model credentials and runs on localhost port 5020.
It uses Rasa Pro 3.21.0.dev5. No Pipecat environment is needed for this LiveKit bot.

With the public Rasa server running, from this project:

```sh
.venv/bin/python run_text_demo.py --room public-juniper-room --participant public-caller --message 'Is maintenance planned for north?'
.venv/bin/python run_text_demo.py --room public-juniper-room --participant public-caller --message 'And for central?'
```

These reader commands invoke your configured Rasa model. Inspect the wording
against both public records, then the missing-area and retry paths. New room
or participant labels select a separate public conversation; changing labels
is not customer authentication. Keep the correct sender stable when continuity
is intended.

## Insert into the LiveKit bot you already own

Keep existing credentials, provider extras, component construction and worker
entrypoint. The core lock qualifies the text adapter; qualify your existing
bot's combined dependency lock and actual speech services separately. In its
async entrypoint, after selecting the intended participant:

```python
import asyncio
from aiohttp import ClientSession
from rasa_room.binding import Conversation
from rasa_room.client import RasaRest
from rasa_room.compose import compose

# ctx, existing_stt, existing_tts and existing_turn_detector are your bot's.
participant = await ctx.wait_for_participant()
conversation = Conversation(ctx.room.name, participant.identity)
async with ClientSession() as http:
    session, agent, options = compose(
        ctx.room, conversation,
        RasaRest(http, "http://127.0.0.1:5020/webhooks/rest/webhook").ask,
        stt=existing_stt, tts=existing_tts,
        turn_detection=existing_turn_detector,
    )
    closed = asyncio.Event()
    session.on("close", lambda event: closed.set())
    try:
        await session.start(room=ctx.room, agent=agent, room_options=options)
        await closed.wait()
    finally:
        await session.aclose()
```

This constructs an actual AgentSession with the retained speech objects,
native model adapter and explicitly selected participant. It retains LiveKit's
normal close-on-disconnect policy; start a new session/adapter for a new linked
participant rather than rebinding a model that owns another conversation.
If your bot deliberately keeps sessions across reconnects or switches
participants, design that lifecycle and requalify the participant ownership.
The delayed-reader controls expose the completion-time check; they do not
justify retaining an old dialogue binding when a new customer takes over.

The configured Rasa endpoint owns dialogue history and tools. LiveKit retains
media and turn detection. Keep one TTS path and your transport event handlers;
perform acoustic interruption and session-recovery acceptance on the combined bot.

## Retire the completed experiment

After your own bot/server and requests finish, retain needed state, recordings
and models. From the repository root:

```sh
python3 scripts/workspace.py retire tutorials/frameworks-with-rasa/livekit --owner juniper-room-demo --inactive
```

Retire a selected Rasa environment only if you created it and no experiment
still depends on it. Keep source, locks and qualification records.
