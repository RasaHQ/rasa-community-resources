# SPDX-License-Identifier: MIT
"""Which generated Banking Hub model belongs to each request and reply this example uses.

bh_demo/vendor_models/ is generated (make models); this small map is written by
hand. The models give the client typed request bodies and replies, with Python
names in snake_case and Fiserv's names as aliases on the wire. They do not
replace the OpenAPI validators in contract.py, which stay the authority: every
request and reply is still validated against the pinned release on the wire.
"""
from __future__ import annotations

from pydantic import BaseModel
from pydantic.experimental.missing_sentinel import MISSING

from .vendor_models import acct, party, xfer

REQUEST: dict[str, type[BaseModel]] = {
    "party": party.PartyAcctRelInqRqType,
    "acct": acct.AcctInqRqType,
    "xfer": xfer.XferAddRqType,
}
# The success reply of each operation (201 for the transfer, 200 for the reads).
REPLY: dict[str, type[BaseModel]] = {
    "party": party.PartyAcctRelInqRsType,
    "acct": acct.AcctInqRsType,
    "xfer": xfer.XferAddRsType,
}


def request_body(key: str, value: dict) -> dict:
    """A request body built through its model: a missing required field or a wrong type fails here."""
    return REQUEST[key].model_validate(value).model_dump(mode="json", by_alias=True, exclude_unset=True)


def present(value):
    """An optional field's value, or None when the reply left it out (MISSING)."""
    return None if value is MISSING else value


def reply(key: str, data) -> BaseModel:
    """The success reply as its model."""
    return REPLY[key].model_validate(data)
