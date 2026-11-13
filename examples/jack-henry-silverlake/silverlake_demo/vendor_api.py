# SPDX-License-Identifier: MIT
"""Which generated jXchange dataclass belongs to each request and reply this example uses.

silverlake_demo/vendor_models/ is generated (make models); this module is
written by hand. It turns a request dataclass into the body element the client
sends, and a reply body element into its dataclass, with xsdata's XML
serializer and parser, and runs every dataclass through a Pydantic TypeAdapter
on the way in and out.

What the TypeAdapter checks, in strict mode and on every nested object: each
field holds exactly its declared type (the generated class itself, not another
class or a dict; Decimal, int, str, bool or xsdata's XmlDate and similar as the
very type, with no conversion from text), a required field is present and not
None, and a list field holds only its item type. It does not check the XML
schema's facets (lengths, patterns, digits, ranges), how often an element may
repeat, choices or element order: the xmlschema validation in contract.py
stays the full wire check, before every send and on every reply.

The pinned schemas declare most optional elements nillable, so xsdata would
write an optional field left as None as xsi:nil. The serializer here leaves
such a field out instead, so an optional field left out stays absent on the
wire. A reply's nil and absent both read as None.

AcctInqResponse has no generated class (its reply tree is about 49,000
generated lines). For it, the client reads only the loan payment record at
LOAN_PAYMENT_PATH, which is parsed into LOAN_PAYMENT.
"""
from __future__ import annotations

import dataclasses
import inspect
import xml.etree.ElementTree as ET

from pydantic import ConfigDict, TypeAdapter, ValidationError
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.parsers.config import ParserConfig
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

from .contract import NS
from .vendor_models import inquiry, transaction

REQUEST = {
    "AcctSrch": inquiry.AcctSrch,
    "AcctBalInq": inquiry.AcctBalInq,
    "AcctHistSrch": inquiry.AcctHistSrch,
    "AcctInq": inquiry.AcctInq,
    "LnPayoffInq": inquiry.LnPayoffInq,
    "XferAdd": transaction.XferAdd,
}
REPLY = {
    "AcctSrch": inquiry.AcctSrchResponse,
    "AcctBalInq": inquiry.AcctBalInqResponse,
    "AcctHistSrch": inquiry.AcctHistSrchResponse,
    "LnPayoffInq": inquiry.LnPayoffInqResponse,
    "XferAdd": transaction.XferAddResponse,
}
# AcctInqResponse: only this record is modelled (see the module docstring).
LOAN_PAYMENT_PATH = ("LnAcctInqRec", "x_LnInfoRec", "LnInfoRec")
LOAN_PAYMENT = inquiry.LnInfoRecCtype


class ModelError(Exception):
    """A body does not fit its generated model. Closed and redacted, like ContractError."""


# Strict, and every instance is checked again field by field (Pydantic otherwise
# accepts any instance of a standard dataclass as it is). XmlDate and the other
# xsdata value types are checked as plain instances of their class.
_STRICT = ConfigDict(strict=True, revalidate_instances="always", arbitrary_types_allowed=True)
for _module in (inquiry, transaction):
    for _cls in vars(_module).values():
        if inspect.isclass(_cls) and dataclasses.is_dataclass(_cls) and _cls.__module__ == _module.__name__:
            _cls.__pydantic_config__ = _STRICT

_ADAPTERS: dict[type, TypeAdapter] = {}
_CONTEXT = XmlContext()
_PARSER = XmlParser(context=_CONTEXT, config=ParserConfig(
    fail_on_unknown_properties=True, fail_on_unknown_attributes=True, fail_on_converter_warnings=True))


class _Serializer(XmlSerializer):
    """xsdata's serializer, except that an optional field left as None is not written (no xsi:nil)."""

    @classmethod
    def next_value(cls, obj, meta):
        for var, value in super().next_value(obj, meta):
            if value is None and not var.required:
                continue
            yield var, value


_SERIALIZER = _Serializer(context=_CONTEXT, config=SerializerConfig(xml_declaration=False))


def adapter(cls: type) -> TypeAdapter:
    if cls not in _ADAPTERS:
        _ADAPTERS[cls] = TypeAdapter(cls)
    return _ADAPTERS[cls]


def checked(model):
    """The model after the strict TypeAdapter check; ModelError if any field has the wrong type."""
    try:
        return adapter(type(model)).validate_python(model)
    except ValidationError:
        raise ModelError("model_mismatch") from None


def to_element(model) -> ET.Element:
    """A request dataclass as the body element to validate and send."""
    if type(model) not in REQUEST.values():
        raise ModelError("unsupported_request")
    try:
        text = _SERIALIZER.render(checked(model), ns_map={None: NS})
        return ET.fromstring(text)
    except ModelError:
        raise
    except Exception:
        raise ModelError("model_mismatch") from None


def parse(cls: type, element: ET.Element):
    """One body element (already validated against the schema) as its dataclass."""
    try:
        model = _PARSER.from_bytes(ET.tostring(element, encoding="utf-8"), cls)
    except Exception:
        raise ModelError("model_mismatch") from None
    return checked(model)


def reply(operation: str, body: ET.Element):
    """The reply body as its dataclass; for AcctInq, the loan payment record or None."""
    if operation == "AcctInq":
        node = body
        for name in LOAN_PAYMENT_PATH:
            node = node.find("{%s}%s" % (NS, name)) if node is not None else None
        return parse(LOAN_PAYMENT, node) if node is not None else None
    return parse(REPLY[operation], body)


def reply_element(model, element: str | None = None) -> ET.Element:
    """A reply dataclass (the mock's replies) as its body element, after the strict check.

    For LOAN_PAYMENT, `element` names the element it becomes (LnInfoRec). A field
    of the wrong type fails here with ModelError, before the reply is sent."""
    if type(model) not in REPLY.values() and type(model) is not LOAN_PAYMENT:
        raise ModelError("unsupported_reply")
    try:
        return ET.fromstring(to_xml(model, element))
    except ModelError:
        raise
    except Exception:
        raise ModelError("model_mismatch") from None


def to_xml(model, element: str | None = None) -> str:
    """Any generated dataclass as XML text (tests use it for reply round trips).

    A class generated from a complex type (such as LOAN_PAYMENT) has no element
    name of its own; `element` names the element it was read from.
    """
    text = _SERIALIZER.render(checked(model), ns_map={None: NS})
    if element is None:
        return text
    root = ET.fromstring(text)
    root.tag = "{%s}%s" % (NS, element)
    return ET.tostring(root, encoding="unicode")
