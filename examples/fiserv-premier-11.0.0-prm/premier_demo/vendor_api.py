# SPDX-License-Identifier: MIT
"""Which generated Premier model belongs to each request and reply this example uses.

premier_demo/vendor_models/ is generated (make models); this small map is
written by hand. The models give the client typed request bodies and replies,
with Python names in snake_case and Fiserv's names as aliases on the wire. They
do not replace the OpenAPI validators in contract.py, which stay the authority:
every request and reply is still validated against the pinned definitions.
"""
from __future__ import annotations

from pydantic import BaseModel

from .vendor_models import dda, loan, party, trn, xfer

REQUEST: dict[str, type[BaseModel]] = {
    "party": party.PartyAcctRelInqBySecuredRequest,
    "dda": dda.GetAccountsSecuredRequest,
    "loan": loan.GetAccountsSecuredRequest,
    "trn": trn.AcctTrnInqOperBySecuredRequest,
    "xfer": xfer.XferAddOperRequest,
}
# The success reply of each definition (201 for the transfer, 200 for the reads).
REPLY: dict[str, type[BaseModel]] = {
    "party": party.PartyAcctRelInqBySecuredResponse,
    "dda": dda.GetAccountsSecuredResponse,
    "loan": loan.GetAccountsSecuredResponse,
    "trn": trn.AcctTrnInqOperBySecuredResponse,
    "xfer": xfer.XferAddOperResponse,
}


def request_body(key: str, value: dict) -> dict:
    """A request body built through its model: a missing required field or a wrong type fails here."""
    return REQUEST[key].model_validate(value).model_dump(mode="json", by_alias=True, exclude_unset=True)


def reply(key: str, data) -> BaseModel:
    """The success reply as its model."""
    return REPLY[key].model_validate(data)
