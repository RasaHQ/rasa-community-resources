# SPDX-License-Identifier: MIT
"""The generated jXchange dataclasses match the example's own recorded traffic.

Equivalence used throughout: two XML bodies are the same when their Canonical
XML 2.0 forms are identical (xml.etree.ElementTree.canonicalize with
rewrite_prefixes=True, so only the namespace prefix spelling may differ). With
the pinned archive present, the round-tripped bodies are also validated with the
example's own xmlschema validators and decoded by them to the same data.

AcctInqResponse has no generated class: for it, the loan payment record the
client reads (LnAcctInqRec / x_LnInfoRec / LnInfoRec) is what round-trips.
"""
import dataclasses
from decimal import Decimal
import importlib.util
import typing
import unittest
import xml.etree.ElementTree as ET

import httpx

from silverlake_demo.client import SilverLakeClient, Unavailable
from silverlake_demo.compat import PROBES
from silverlake_demo.contract import NS, SOAP_ENV, MissingContractInput, open_envelope
from silverlake_demo.recorded_exchanges import EXCHANGES
from silverlake_demo.vendor_api import (LOAN_PAYMENT, LOAN_PAYMENT_PATH, REPLY, REQUEST, ModelError, parse,
                                        to_element, to_xml)
from silverlake_demo.vendor_models import inquiry, transaction


def canonical(xml) -> str:
    text = xml if isinstance(xml, str) else ET.tostring(xml, encoding="unicode")
    return ET.canonicalize(text, rewrite_prefixes=True)


def modelled(operation, side, xml):
    """(dataclass, element) for one recorded body: the element that has a generated class."""
    element = ET.fromstring(xml)
    if side == "request":
        return REQUEST[operation], element
    if operation == "AcctInq":
        for name in LOAN_PAYMENT_PATH:
            element = element.find("{%s}%s" % (NS, name))
        return LOAN_PAYMENT, element
    return REPLY[operation], element


def recorded(operation, side, index=0) -> str:
    return [xml for name, kind, xml in EXCHANGES if (name, kind) == (operation, side)][index]


def round_trip(operation, side, xml):
    cls, element = modelled(operation, side, xml)
    model = parse(cls, element)
    return element, model, to_xml(model, LOAN_PAYMENT_PATH[-1] if cls is LOAN_PAYMENT else None)


class StubContract:
    """Schema validation is the job of the archive tests below; these run without vendor files."""

    actions = {name: "http://jackhenry.com/ws/" + name for name in REQUEST}

    def validate(self, element):
        pass


def soap(body_xml: str) -> bytes:
    return ('<soap:Envelope xmlns:soap="%s"><soap:Header/><soap:Body>%s</soap:Body></soap:Envelope>'
            % (SOAP_ENV, body_xml)).encode()


class Replay:
    """A transport that answers with the recorded replies, in order, and keeps every request body sent."""

    def __init__(self, replies=None):
        self.replies = list(replies if replies is not None else
                            [xml for _, side, xml in EXCHANGES if side == "response"])
        self.sent = []

    def __call__(self, request):
        self.sent.append(open_envelope(request.content))
        return httpx.Response(200, content=soap(self.replies.pop(0)))


class RecordedTrafficRoundTrip(unittest.TestCase):
    def test_every_recorded_body_comes_back_unchanged_through_its_dataclass(self):
        for operation, side, xml in EXCHANGES:
            with self.subTest(operation=operation, side=side):
                element, _, again = round_trip(operation, side, xml)
                self.assertEqual(canonical(again), canonical(element))
                self.assertNotIn("nil", again)
        self.assertEqual(len(EXCHANGES), 16)

    def test_every_operation_has_a_request_and_a_reply_model(self):
        operations = {operation for operation, _, _ in EXCHANGES}
        self.assertEqual(set(REQUEST), operations)
        self.assertEqual(set(REPLY), operations - {"AcctInq"})  # AcctInq: the loan payment record only

    def test_the_client_sends_exactly_the_recorded_requests_and_reads_the_same_values(self):
        replay = Replay()
        client = SilverLakeClient(StubContract(), "http://127.0.0.1:9", transport=httpx.MockTransport(replay))
        self.assertEqual(client.accounts("C100001"), PROBES[0][2])
        self.assertEqual(client.available_balance("1001001", "D"), PROBES[1][2])
        self.assertEqual(client.history("1001001", "D"), PROBES[2][2])
        self.assertEqual(client.history("1001001", "D", cursor="3")[1], None)
        self.assertEqual(client.loan_payment("7001001"), PROBES[3][2])
        self.assertEqual(client.payoff("7001001", "2026-11-20"), PROBES[4][2])
        with self.assertRaises(Unavailable):
            client.payoff("7001001", "2026-12-24")  # the reply has no PayoffAmt
        self.assertEqual(client.transfer(("1001001", "D"), ("1001002", "S"), Decimal("25.00")), "accepted")
        recorded = [xml for _, side, xml in EXCHANGES if side == "request"]
        self.assertEqual([canonical(element) for element in replay.sent], [canonical(xml) for xml in recorded])


class OptionalFields(unittest.TestCase):
    def test_an_optional_field_left_out_stays_absent_and_one_set_is_present(self):
        def request(cursor):
            return inquiry.AcctHistSrch(
                srch_msg_rq_hdr=inquiry.SrchMsgRqHdrCtype(
                    j_xchange_hdr=inquiry.JXchangeHdrCtype(audit_usr_id=inquiry.AuditUsrIdType(value="a"),
                                                           audit_ws_id=inquiry.AuditWsIdType(value="b")),
                    max_rec=inquiry.MaxRecType(value=3),
                    cursor=inquiry.CursorType(value=cursor) if cursor else None),
                in_acct_id=inquiry.AccountIdCtype(acct_id=inquiry.AcctIdType(value="1001001"),
                                                  acct_type=inquiry.AcctTypeType(value="D")))
        without, with_cursor = to_element(request(None)), to_element(request("3"))
        cursor = "{%s}SrchMsgRqHdr/{%s}Cursor" % (NS, NS)
        self.assertIsNone(without.find(cursor))
        self.assertEqual(with_cursor.find(cursor).text, "3")
        self.assertNotIn(b"nil", ET.tostring(without))  # the schema says nillable; left out is not nil

    def test_an_optional_reply_field_left_out_reads_as_none_and_is_not_written_back(self):
        element = ET.fromstring(recorded("AcctBalInq", "response"))
        element.remove(element.find("{%s}AvlBal" % NS))
        model = parse(inquiry.AcctBalInqResponse, element)
        self.assertIsNone(model.avl_bal)
        self.assertEqual(model.cur_bal.value, Decimal("1275.00"))
        self.assertEqual(canonical(to_xml(model)), canonical(element))
        replay = Replay([ET.tostring(element, encoding="unicode")])
        client = SilverLakeClient(StubContract(), "http://127.0.0.1:9", transport=httpx.MockTransport(replay))
        with self.assertRaises(Unavailable) as raised:
            client.available_balance("1001001", "D")  # never CurBal
        self.assertEqual(str(raised.exception), "no_available_balance")

    def test_a_payoff_reply_without_an_amount_keeps_it_absent(self):
        model = parse(inquiry.LnPayoffInqResponse, ET.fromstring(recorded("LnPayoffInq", "response", 1)))
        self.assertIsNone(model.payoff_amt)
        self.assertEqual(str(model.eff_dt.value), "2026-12-24")
        self.assertNotIn("PayoffAmt", to_xml(model))


AMOUNTS = ("9007199254740993", "0.1", "0.2", "1250.07")  # 2**53 + 1 and values float cannot hold exactly


def with_text(xml: str, path: tuple[str, ...], text: str) -> str:
    element = ET.fromstring(xml)
    element.find("/".join("{%s}%s" % (NS, name) for name in path)).text = text
    return ET.tostring(element, encoding="unicode")


class ExactAmounts(unittest.TestCase):
    """Money is Decimal from the wire text to the reply value and back; it never passes through float."""

    def client(self, replies):
        replay = Replay(replies)
        return SilverLakeClient(StubContract(), "http://127.0.0.1:9", transport=httpx.MockTransport(replay)), replay

    def test_every_amount_field_the_client_reads_or_sends_is_typed_decimal(self):
        for cls in (inquiry.AvlBalType, inquiry.PmtAmtDueType, inquiry.PayoffAmtType, inquiry.AmtType,
                    transaction.AmtType):
            with self.subTest(cls=cls.__name__):
                self.assertIs(typing.get_type_hints(cls)["value"], Decimal)
        for module in (inquiry, transaction):  # and no generated field anywhere is a float
            for cls in vars(module).values():
                if dataclasses.is_dataclass(cls) and cls.__module__ == module.__name__:
                    hints = typing.get_type_hints(cls)
                    self.assertFalse([name for name, hint in hints.items() if "float" in str(hint)], cls.__name__)

    def test_available_balance_loan_payment_and_payoff_are_exact(self):
        for text in AMOUNTS:
            expected = format(Decimal(text).quantize(Decimal("0.01")), "f")
            with self.subTest(amount=text):
                client, _ = self.client([with_text(recorded("AcctBalInq", "response"), ("AvlBal",), text)])
                self.assertEqual(client.available_balance("1001001", "D"), expected)
                client, _ = self.client([with_text(recorded("AcctInq", "response"),
                                                   (*LOAN_PAYMENT_PATH, "PmtAmtDue"), text)])
                self.assertEqual(client.loan_payment("7001001")["amount_due"], expected)
                client, _ = self.client([with_text(recorded("LnPayoffInq", "response"), ("PayoffAmt",), text)])
                self.assertEqual(client.payoff("7001001", "2026-11-20")["amount"], expected)
                model = parse(inquiry.AcctBalInqResponse, ET.fromstring(
                    with_text(recorded("AcctBalInq", "response"), ("AvlBal",), text)))
                self.assertEqual(model.avl_bal.value, Decimal(text))
                self.assertIs(type(model.avl_bal.value), Decimal)
        self.assertEqual(format(Decimal("9007199254740993").quantize(Decimal("0.01")), "f"), "9007199254740993.00")
        self.assertNotEqual(float("9007199254740993"), 9007199254740993)  # what float would have lost

    def test_the_transfer_request_carries_the_reviewed_amount_exactly(self):
        for text in (*AMOUNTS, "25.50", "0.10"):
            with self.subTest(amount=text):
                client, replay = self.client([recorded("XferAdd", "response")])
                self.assertEqual(client.transfer(("1001001", "D"), ("1001002", "S"), Decimal(text)), "accepted")
                sent = replay.sent[0].find("{%s}XferRec/{%s}Amt" % (NS, NS)).text
                self.assertEqual(sent, text)
                self.assertEqual(Decimal(sent), Decimal(text))


class TypeAdapterChecks(unittest.TestCase):
    """What the strict TypeAdapter refuses before anything is serialized or read."""

    def transfer(self, **changes):
        fields = dict(
            msg_rq_hdr=transaction.MsgRqHdrCtype(j_xchange_hdr=transaction.JXchangeHdrCtype(
                audit_usr_id=transaction.AuditUsrIdType(value="a"), audit_ws_id=transaction.AuditWsIdType(value="b"))),
            acct_id_from=transaction.AcctIdFromCtype(from_acct_id=transaction.AcctIdType(value="1001001")),
            xfer_rec=transaction.XferRecCtype(amt=transaction.AmtType(value=Decimal("1.00"))))
        fields.update(changes)
        return transaction.XferAdd(**fields)

    def test_a_good_request_passes(self):
        self.assertEqual(to_element(self.transfer()).tag, "{%s}XferAdd" % NS)

    def test_wrong_types_and_missing_required_fields_are_refused(self):
        for changes in ({"xfer_rec": transaction.XferRecCtype(amt=transaction.AmtType(value="1.00"))},  # text, not Decimal
                        {"xfer_rec": transaction.XferRecCtype(amt=transaction.AmtType(value=Decimal("NaN")))},
                        {"acct_id_from": None},  # required
                        {"acct_id_from": inquiry.AccountIdCtype(acct_id=inquiry.AcctIdType(value="1"),
                                                                acct_type=inquiry.AcctTypeType(value="D"))}):
            with self.subTest(changes=list(changes)), self.assertRaises(ModelError):
                to_element(self.transfer(**changes))

    def test_a_reply_value_that_is_not_its_type_is_refused(self):
        xml = recorded("AcctBalInq", "response")
        bad = ET.fromstring(xml)
        bad.find("{%s}AvlBal" % NS).text = "not a number"
        with self.assertRaises(ModelError):
            parse(inquiry.AcctBalInqResponse, bad)
        model = parse(inquiry.AcctBalInqResponse, ET.fromstring(xml))
        with self.assertRaises(ModelError):
            to_xml(dataclasses.replace(model, avl_bal=Decimal("1")))  # a bare Decimal is not an AvlBal_Type


def decoded(schema, element):
    """The body as the example's xmlschema validator decodes it (in memory, no file or network access)."""
    import xmlschema
    return schema.to_dict(xmlschema.XMLResource(element, allow="none", defuse="always"))


class WithThePinnedArchive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.support import load_contract
        cls.contract = load_contract()  # skips without the learner-supplied archive

    def test_round_tripped_bodies_still_validate_and_decode_to_the_same_data(self):
        checked = 0
        for operation, side, xml in EXCHANGES:
            with self.subTest(operation=operation, side=side):
                element, model, again = round_trip(operation, side, xml)
                if operation == "AcctInq" and side == "response":
                    # Put the round-tripped record back in its reply, then validate the whole reply.
                    whole = ET.fromstring(xml)
                    parent = whole.find("{%s}%s/{%s}%s" % (NS, LOAN_PAYMENT_PATH[0], NS, LOAN_PAYMENT_PATH[1]))
                    index = list(parent).index(parent.find("{%s}%s" % (NS, LOAN_PAYMENT_PATH[2])))
                    parent[index] = ET.fromstring(again)
                    original, again_element = ET.fromstring(xml), whole
                else:
                    original, again_element = element, ET.fromstring(again)
                self.contract.validate(again_element)
                schema = self.contract.schema_for(original.tag.split("}", 1)[1])
                self.assertEqual(decoded(schema, again_element), decoded(schema, original))
                checked += 1
        self.assertEqual(checked, 16)


@unittest.skipUnless(importlib.util.find_spec("toposort") and importlib.util.find_spec("ruff"),
                     "the models group is not installed (uv sync --group models)")
class Regeneration(unittest.TestCase):
    def test_the_committed_models_match_a_fresh_generation_from_the_pinned_archive(self):
        from silverlake_demo.contract import default_path
        if not default_path().is_file():
            self.skipTest(str(MissingContractInput("vendor definitions not supplied")))
        import make_models
        self.assertEqual(make_models.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
