# SPDX-License-Identifier: MIT
"""Register the local host-reply policy with the runtime hook loader."""
from rasa.mantle.hooks import modify_model_response
from rasa.mantle.hooks.payloads import ModelResponsePayload
from lib.reply_policy import keep_host_reply_once


@modify_model_response()
async def banking_host_reply(payload: ModelResponsePayload) -> ModelResponsePayload:
    return await keep_host_reply_once(payload)
