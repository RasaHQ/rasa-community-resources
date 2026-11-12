# SPDX-License-Identifier: MIT
"""Await actual channel input before the model; errors stop the turn."""
from rasa.mantle.hooks import modify_incoming_message
from rasa.mantle.hooks.exceptions import HookRejection
from rasa.mantle.hooks.payloads import IncomingMessagePayload
from native_adapter import incoming


@modify_incoming_message(timeout_ms=12000)
async def observe_actual_input(payload: IncomingMessagePayload) -> IncomingMessagePayload:
    try:
        return await incoming(payload)
    except Exception as error:
        raise HookRejection('The transfer outcome may be unknown. Do not retry or request another transfer. Check status when the private fictional host is available.') from error
