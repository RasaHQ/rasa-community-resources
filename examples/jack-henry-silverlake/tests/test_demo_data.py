"""Seeded demo data. Vendor-free: no schema archive is needed."""
from datetime import date, timedelta
from decimal import Decimal
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from xsdata.models.datatype import XmlDate

from silverlake_demo import demo_data, vendor_api
from silverlake_demo.client import SilverLakeClient, _header
from silverlake_demo.contract import q, sub
from silverlake_demo.mock import ACCOUNTS, CUSTOMERS, HISTORY, SilverLakeMock, money
from silverlake_demo.vendor_api import ModelError
from silverlake_demo.vendor_models import inquiry
from tests.support import load_contract

SEEDS = range(1, 201)
LATEST = date(2026, 11, 4)  # the reference data's latest transaction date


def shape(value):
    """The structure of a value: dict keys and element types, not the values themselves."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, shape(value[0]) if value else None)
    return type(value).__name__


class ReferenceSeed(unittest.TestCase):
    def test_seed_zero_is_the_reference_data(self):
        self.assertEqual(demo_data.REFERENCE_SEED, 0)
        data = demo_data.generate(0)
        self.assertEqual(data, {"customers": CUSTOMERS, "accounts": ACCOUNTS, "history": HISTORY})

    def test_seed_zero_is_a_copy(self):
        data = demo_data.generate(0)
        data["accounts"]["1001001"]["avail"] = 1
        data["accounts"]["7001001"]["payoff"]["2026-11-20"] = 1
        data["history"]["1001001"].clear()
        self.assertEqual(ACCOUNTS["1001001"]["avail"], 125000)
        self.assertEqual(ACCOUNTS["7001001"]["payoff"]["2026-11-20"], 412055)
        self.assertEqual(len(HISTORY["1001001"]), 5)

    def test_bad_seeds_are_refused(self):
        for seed in (-1, 1_000_000, True, 1.5, "3"):
            with self.assertRaises(ValueError):
                demo_data.generate(seed)


class Reproducible(unittest.TestCase):
    def test_same_seed_same_data(self):
        self.assertEqual(demo_data.generate(4242), demo_data.generate(4242))

    def test_different_seeds_differ(self):
        self.assertNotEqual(demo_data.generate(1), demo_data.generate(2))
        self.assertNotEqual(demo_data.generate(1), demo_data.generate(0))

    def test_global_random_state_is_untouched(self):
        import random
        random.seed(99)
        expected = random.random()
        random.seed(99)
        demo_data.generate(77)
        self.assertEqual(random.random(), expected)


class Invariants(unittest.TestCase):
    def test_invariants_hold_for_many_seeds(self):
        reference_shape = shape(demo_data.generate(0))
        for seed in SEEDS:
            with self.subTest(seed=seed):
                data = demo_data.generate(seed)
                self.assertEqual(shape(data), reference_shape)
                self.assertEqual(data["customers"], CUSTOMERS)
                self.assertEqual(set(data["accounts"]), set(ACCOUNTS))
                self.assertEqual(set(data["history"]), set(HISTORY))
                for ident, account in data["accounts"].items():
                    self.check_account(ident, account)
                for ident, rows in data["history"].items():
                    self.check_history(ident, rows)

    def check_account(self, ident, account):
        ref = ACCOUNTS[ident]
        for key in ("type", "cust", "desc", "next_pay", "next_sched"):
            self.assertEqual(account.get(key), ref.get(key))
        self.assertEqual(set(account), set(ref))
        for key, value in account.items():
            if key not in ("type", "cust", "desc", "next_pay", "next_sched", "payoff"):
                self.assertIs(type(value), int, key)  # whole cents
        if ref["type"] in {"D", "S"}:
            self.assertGreaterEqual(account["avail"], demo_data.DEPOSIT_FLOOR)
            self.assertLessEqual(account["avail"], account["cur"])
            self.assertLessEqual(account["cur"], 2.5 * ref["cur"])
            if ref["type"] == "S":
                self.assertEqual(account["avail"], account["cur"])
        else:
            self.assertGreater(account["regular"], 0)
            self.assertGreaterEqual(account["past_due"], 0)
            self.assertEqual(account["due"], account["regular"] + account["past_due"])
            self.assertTrue(0.6 * ref["regular"] <= account["regular"] <= 1.4 * ref["regular"])
            self.assertEqual(set(account["payoff"]), set(ref["payoff"]))  # same quote dates only
            quotes = [amount for _, amount in sorted(account["payoff"].items())]
            self.assertEqual(quotes, sorted(quotes))  # a later quote is never lower
            for amount in quotes:
                self.assertIs(type(amount), int)
                self.assertGreater(amount, account["due"])

    def check_history(self, ident, rows):
        kind = ACCOUNTS[ident]["type"]
        low, high = demo_data.CHECKING_ROWS if kind == "D" else demo_data.SAVINGS_ROWS
        self.assertTrue(low <= len(rows) <= high)
        self.assertGreaterEqual(len(rows), 3)  # at least one full page of the mock's default size
        posted = [row[0] for row in rows]
        self.assertEqual(posted, sorted(posted, reverse=True))  # newest first, like the reference
        for when, cents, text in rows:
            day = date.fromisoformat(when)
            self.assertEqual(when, day.isoformat())
            self.assertTrue(LATEST - timedelta(days=demo_data.HISTORY_DAYS) < day <= LATEST)
            self.assertIs(type(cents), int)
            self.assertNotEqual(cents, 0)
            self.assertTrue(text.startswith("Fictional "))
        if kind == "D":
            self.assertTrue(any(cents < 0 for _, cents, _ in rows))
            self.assertTrue(any(text == "Fictional Payroll" for _, _, text in rows))
        else:
            self.assertTrue(any(cents > 0 for _, cents, _ in rows))


class MockUsesData(unittest.TestCase):
    """The mock's handlers read the data they were given; no schema is needed to call them directly."""

    def test_default_is_the_reference_data(self):
        self.assertEqual(SilverLakeMock(None).accounts, ACCOUNTS)

    def test_seeded_data_reaches_the_replies(self):
        data = demo_data.generate(31337)
        fake = SilverLakeMock(None, data=data)
        request = ET.Element(q("AcctBalInq"))
        node = sub(request, "InAcctId")
        sub(node, "AcctId", "1001001")
        sub(node, "AcctType", "D")
        reply = fake.acct_bal_inq(request)
        cents = data["accounts"]["1001001"]["avail"]
        self.assertEqual(reply.find(q("AvlBal")).text, f"{cents // 100}.{cents % 100:02d}")
        request = ET.Element(q("AcctHistSrch"))
        node = sub(request, "InAcctId")
        sub(node, "AcctId", "1001001")
        sub(node, "AcctType", "D")
        hdr = fake.acct_hist_srch(request).find(q("SrchMsgRsHdr"))
        self.assertEqual(hdr.findtext(q("MoreRec")), "true")  # more than one page of three


class ChooseSeed(unittest.TestCase):
    def test_demo_seed_is_honoured(self):
        self.assertEqual(demo_data.choose_seed({"DEMO_SEED": "0"}), 0)
        self.assertEqual(demo_data.choose_seed({"DEMO_SEED": "123456"}), 123456)
        self.assertEqual(demo_data.choose_seed({"DEMO_SEED": " 999999 "}), 999999)

    def test_bad_values_are_refused_plainly(self):
        for text in ("", "abc", "-1", "1000000", "1.5", "1e3", "0x10", "٣"):
            with self.subTest(text=text), self.assertRaises(ValueError) as raised:
                demo_data.choose_seed({"DEMO_SEED": text})
            self.assertIn("0 to 999999", str(raised.exception))

    def test_otherwise_a_fresh_seed_from_1_to_999999(self):
        seeds = {demo_data.choose_seed({}) for _ in range(200)}
        self.assertTrue(all(1 <= seed <= 999999 for seed in seeds))
        self.assertGreater(len(seeds), 1)
        with mock.patch("random.SystemRandom.randrange", return_value=5) as drawn:
            self.assertEqual(demo_data.choose_seed({}), 5)
        drawn.assert_called_once_with(1, 1_000_000)


class SeedLine(unittest.TestCase):
    def test_wording(self):
        self.assertEqual(demo_data.seed_line(4821),
                         "Demo data seed: 4821; set DEMO_SEED=4821 to get the same data again.")
        self.assertEqual(demo_data.seed_line(0),
                         "Demo data seed: 0; set DEMO_SEED=0 to get the same data again."
                         " (reference data, as in the README's checked sequence)")


NO_QUOTE_DATE = "2026-12-24"  # the tests expect this date to have no payoff quote


def replies(fake):
    """Every reply the seeded data feeds: (operation, body element), with every history page."""
    out = []
    for ident, account in sorted(fake.accounts.items()):
        in_acct = SilverLakeClient._in_acct(ident, account["type"])
        if account["type"] in {"D", "S"}:
            out.append(("AcctBalInq", fake.acct_bal_inq(vendor_api.to_element(
                inquiry.AcctBalInq(msg_rq_hdr=_header(inquiry), in_acct_id=in_acct)))))
            cursor = None
            while True:
                body = fake.acct_hist_srch(vendor_api.to_element(inquiry.AcctHistSrch(
                    srch_msg_rq_hdr=_header(inquiry, search=True, max_rec=3, cursor=cursor), in_acct_id=in_acct)))
                out.append(("AcctHistSrch", body))
                cursor = body.findtext(q("SrchMsgRsHdr") + "/" + q("Cursor"))
                if cursor is None:
                    break
        else:
            out.append(("AcctInq", fake.acct_inq(vendor_api.to_element(
                inquiry.AcctInq(msg_rq_hdr=_header(inquiry), in_acct_id=in_acct)))))
            for when in sorted(account["payoff"]) + [NO_QUOTE_DATE]:
                out.append(("LnPayoffInq", fake.ln_payoff_inq(vendor_api.to_element(inquiry.LnPayoffInq(
                    msg_rq_hdr=_header(inquiry), account_id=in_acct,
                    eff_dt=inquiry.EffDtType(value=XmlDate.from_string(when)))))))
    return out


class SeededRepliesFitTheModels(unittest.TestCase):
    """Each seeded reply is built as its generated dataclass; vendor-free."""

    def test_every_seeded_reply_reads_back_as_its_dataclass_unchanged(self):
        for seed in range(0, 201):
            for operation, body in replies(SilverLakeMock(None, data=demo_data.generate(seed))):
                with self.subTest(seed=seed, operation=operation):
                    model = vendor_api.reply(operation, body)  # strict: every field its declared type
                    if operation == "AcctInq":
                        record = body.find(q("LnAcctInqRec")).find(q("x_LnInfoRec")).find(q("LnInfoRec"))
                        again = vendor_api.to_xml(model, "LnInfoRec")
                    else:
                        record, again = body, vendor_api.to_xml(model)
                    self.assertEqual(ET.canonicalize(again, rewrite_prefixes=True),
                                     ET.canonicalize(ET.tostring(record, encoding="unicode"), rewrite_prefixes=True))

    def test_reply_amounts_are_the_seeded_cents(self):
        for seed in (0, 7, 4821):
            data = demo_data.generate(seed)
            fake = SilverLakeMock(None, data=data)
            for operation, body in replies(fake):
                model = vendor_api.reply(operation, body)
                if operation == "AcctBalInq":
                    account = data["accounts"][model.in_acct_id.acct_id.value]
                    self.assertEqual((model.cur_bal.value, model.avl_bal.value),
                                     (money(account["cur"]), money(account["avail"])))
                elif operation == "AcctInq":
                    loan = next(a for a in data["accounts"].values()
                                if a["type"] == "L" and str(model.nxt_pay_dt.value) == a["next_pay"])
                    self.assertEqual(model.pmt_amt_due.value, money(loan["due"]))
                elif operation == "LnPayoffInq":
                    quotes = data["accounts"][model.account_id.acct_id.value]["payoff"]
                    amount = quotes.get(str(model.eff_dt.value))
                    self.assertEqual(model.payoff_amt.value if model.payoff_amt else None,
                                     money(amount) if amount is not None else None)
        self.assertEqual(money(125000), Decimal("1250.00"))
        self.assertEqual(str(money(0)), "0.00")
        with self.assertRaises(TypeError):
            money(1250.0)  # a float is never money

    def test_a_value_that_does_not_fit_the_model_fails_when_the_reply_is_built(self):
        data = demo_data.generate(0)
        data["accounts"]["7001001"]["next_pay"] = "next week"  # not a date
        fake = SilverLakeMock(None, data=data)
        with self.assertRaises((ModelError, ValueError)):
            fake.acct_inq(vendor_api.to_element(inquiry.AcctInq(
                msg_rq_hdr=_header(inquiry), in_acct_id=SilverLakeClient._in_acct("7001001", "L"))))


class SeededRepliesFitThePinnedSchemas(unittest.TestCase):
    """The same replies against the pinned jXchange schemas (needs the vendor archive)."""

    def test_every_seeded_reply_validates_against_the_pinned_schemas(self):
        contract = load_contract()
        for seed in range(0, 201):
            for operation, body in replies(SilverLakeMock(contract, data=demo_data.generate(seed))):
                with self.subTest(seed=seed, operation=operation):
                    contract.validate(body)


if __name__ == "__main__":
    unittest.main()
