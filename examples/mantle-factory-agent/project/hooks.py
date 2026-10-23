"""Buffer deterministic responses through the pinned Mantle response hook."""
from rasa.mantle.hooks import ModelResponsePayload, modify_model_response


@modify_model_response()
async def buffered_scripted_reply(response: ModelResponsePayload) -> ModelResponsePayload:
    # A registered response modifier requests normal non-streaming delivery.
    # The scripted client returns complete, gate-derived text; no provider runs.
    return response
