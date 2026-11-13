# SPDX-License-Identifier: MIT
"""Which generated Banking Hub model belongs to each request and reply this example uses.

bh_demo/vendor_models/ is generated (make models); this small map is written by
hand. The models give the client typed request bodies and replies, with Python
names in snake_case and Fiserv's names as aliases on the wire. They do not
replace the OpenAPI validators in contract.py, which stay the authority: every
request and reply is still validated against the pinned release on the wire.
"""
from __future__ import annotations

from decimal import Decimal
import json

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
    """A request body built through its model: a missing required field or a wrong type fails here.

    Numbers stay exact Decimal; see plain()."""
    return plain(REQUEST[key].model_validate(value))


def reply_body(key: str, value: dict) -> dict:
    """A success reply body built through its model (the mock's replies).

    The value goes through dumps() and loads() first, so a float is refused rather than
    coerced, and the model checks exactly what the wire will carry: a missing required
    field or a value of the wrong type fails here, before the reply is sent."""
    return plain(REPLY[key].model_validate(loads(dumps(value))))


def plain(model: BaseModel):
    """The model as JSON values, with every number as an exact Decimal.

    Pydantic's JSON mode writes enums and dates the way the wire needs them but turns a
    Decimal into a string; Python mode keeps the Decimal. Take the JSON form, and put the
    Decimal back wherever the Python form holds one."""
    options = {"by_alias": True, "exclude_unset": True}
    return _merge(model.model_dump(mode="python", **options), model.model_dump(mode="json", **options))


def _merge(python, as_json):
    if isinstance(python, Decimal):
        return python
    if isinstance(python, dict):
        return {key: _merge(python[key], as_json[key]) for key in python}
    if isinstance(python, list):
        return [_merge(left, right) for left, right in zip(python, as_json)]
    return as_json


def loads(raw) -> object:
    """JSON with every non-integer number read as Decimal, never as a float."""
    return json.loads(raw, parse_float=Decimal)


def dumps(value) -> str:
    """JSON text written directly, with each Decimal as its exact number token.

    No string substitution and no float anywhere: every value is encoded by type, so a
    string field can never be mistaken for a number. A float is refused outright."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("not a finite number")
        return format(value, "f")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON object keys must be strings")
        return "{" + ",".join(json.dumps(key) + ":" + dumps(item) for key, item in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(dumps(item) for item in value) + "]"
    raise TypeError(f"not written to the wire: {type(value).__name__}")  # floats included


def present(value):
    """An optional field's value, or None when the reply left it out (MISSING)."""
    return None if value is MISSING else value


def reply(key: str, data) -> BaseModel:
    """The success reply as its model."""
    return REPLY[key].model_validate(data)
