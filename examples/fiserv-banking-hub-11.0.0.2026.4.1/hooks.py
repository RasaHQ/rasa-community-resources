# SPDX-License-Identifier: MIT
"""Register the local presentation policies with the runtime hook loader."""
from rasa.mantle.hooks import modify_model_request, modify_model_response
from rasa.mantle.hooks.payloads import ModelRequestPayload, ModelResponsePayload
from lib.conversation_policy import add_alias_note, drop_repeated_text
from lib.reply_policy import keep_host_reply_once


@modify_model_request()
async def banking_alias_context(payload: ModelRequestPayload) -> ModelRequestPayload:
    # The caller's permitted aliases come from the host, so the model needs no
    # discovery call and reads nothing aloud between tool calls.
    return add_alias_note(payload)


@modify_model_response()
async def banking_host_reply(payload: ModelResponsePayload) -> ModelResponsePayload:
    return drop_repeated_text(await keep_host_reply_once(payload))
