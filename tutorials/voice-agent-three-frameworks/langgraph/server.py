# concern: voice-loop
"""The LangGraph version's server: browser_audio WebSocket, events endpoint, health.

    uv run python server.py --port 5006

Routes (shared/web/PROTOCOL.md):

- ``/webhooks/browser_audio/websocket``: one call per connection
  (voice_loop.Call). The conversation id is the ``X-Rasa-Sender-Id`` header
  when it is well formed, else ``inspect-<uuid>``; it is the agent's
  ``thread_id`` and the ``conversation_id`` every cedar_clinic call gets.
- ``GET /conversations/{id}/events``: user, bot and bot_turn_ended events.
- ``GET /health``: 200 once the agent is built.
"""

from __future__ import annotations

from cedar_speech.router import create_asr, create_tts

import argparse
import contextlib
import logging
import re
import uuid

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from agent import build_agent
from voice_loop import CONVERSATIONS, Call

SENDER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
WS_PATH = "/webhooks/browser_audio/websocket"


def create_app(agent=None, tts=None, *, use_asr: bool = True) -> Starlette:
    state = {"agent": agent, "tts": tts}

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        state["agent"] = state["agent"] or build_agent()
        state["tts"] = state["tts"] or create_tts()
        yield
        await state["tts"].close()

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok" if state["agent"] is not None else "starting"},
                            status_code=200 if state["agent"] is not None else 503)

    async def events(request: Request) -> JSONResponse:
        conversation = CONVERSATIONS.get(request.path_params["conversation_id"])
        if conversation is None:
            return JSONResponse({"events": []})
        return JSONResponse({"events": list(conversation.events)})

    async def browser_audio(websocket: WebSocket) -> None:
        sender = websocket.headers.get("x-rasa-sender-id", "")
        conversation_id = sender if SENDER_RE.match(sender) else f"inspect-{uuid.uuid4()}"
        await websocket.accept()
        await Call(websocket, conversation_id, state["agent"], state["tts"], use_asr=use_asr).run()

    return Starlette(
        routes=[Route("/health", health), Route("/conversations/{conversation_id}/events", events),
                WebSocketRoute(WS_PATH, browser_audio)],
        lifespan=lifespan,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5006)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
