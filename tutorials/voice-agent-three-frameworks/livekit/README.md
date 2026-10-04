# Cedar Clinic with livekit

A runnable prescription-refill voice tutorial using the community livekit SDK.
The clinic, patient records and calls are fictional. The application connects
the shared clinic tools to browser audio and speech-provider clients.

From the companion root, create only this project's isolated environment:

```sh
python3 scripts/workspace.py start tutorials/voice-agent-three-frameworks/livekit --owner cedar-tutorial
cd tutorials/voice-agent-three-frameworks/livekit
make test
make provider-contract
make confirmation-countertest
```

`make run` starts the browser server. Configure model and speech keys locally
using `.env.example`; never commit credentials or generated output.
The dependency versions are pinned in `pyproject.toml` and `uv.lock`.

The offline commands exercise tool dispatch, confirmation, browser framing
and the model-facing tool schemas without paid provider requests. Inspect
`agent.py`, `guard.py` and `server.py` for the implementation.

After the tutorial and its jobs finish, return to the companion root:

```sh
python3 scripts/workspace.py retire tutorials/voice-agent-three-frameworks/livekit --owner cedar-tutorial --inactive
```
