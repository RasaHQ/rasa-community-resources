"""Make the pinned client's explicit update selection visible at the call site."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict

POLL_TYPES = ('message', 'callback_query')


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, hide_input_in_errors=True)
    allowed_updates: tuple[Literal['message', 'callback_query'], ...]


async def poll_updates(telegram, *, offset, limit, timeout, allowed_updates):
    selection = Selection(allowed_updates=allowed_updates)
    # The maintained pinned client has no selection keyword. Its PUBLIC request
    # model always serializes these exact types on every poll. Refuse drift,
    # then call the public client; never patch its internals or issue a second
    # competing HTTP poll. The installed transport control checks actual JSON.
    from zeo_integrations.telegram.direct_models import GetUpdatesRequest
    if selection.allowed_updates != POLL_TYPES or GetUpdatesRequest().allowed_updates != POLL_TYPES:
        raise ValueError('This client cannot honor the selected Telegram update types')
    return await telegram.get_updates(offset=offset, limit=limit, timeout=timeout)
