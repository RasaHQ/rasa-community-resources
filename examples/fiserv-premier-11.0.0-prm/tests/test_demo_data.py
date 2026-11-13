"""Seeded demo data: seed 0 is the reference data; other seeds vary but keep every invariant.

Vendor-free: nothing here needs the Fiserv download.
"""
from datetime import date
from decimal import Decimal
import unittest
from unittest import mock

from pydantic import ValidationError

from premier_demo import demo_data
from premier_demo.demo_data import REFERENCE_SEED, choose_seed, generate, seed_line
from premier_demo.mock import ACCOUNTS, PAGE, TRANSACTIONS, PremierMock
from premier_demo.vendor_api import REPLY, dumps, loads, plain
from tests.support import load_contract

LATEST = date.fromisoformat(max(row[1] for rows in TRANSACTIONS.values() for row in rows))


class ReferenceData(unittest.TestCase):
    def test_seed_zero_is_the_reference_data(self):
        self.assertEqual(REFERENCE_SEED, 0)
        data = generate(0)
        self.assertEqual(data, {"accounts": ACCOUNTS, "transactions": TRANSACTIONS})
        # A deep copy: changing it never touches the reference constants.
        data["accounts"]["5550010001"]["avail"] = 1
        data["transactions"]["5550010001"].clear()
        self.assertEqual(ACCOUNTS["5550010001"]["avail"], 125000)
        self.assertEqual(len(TRANSACTIONS["5550010001"]), 5)

    def test_mock_defaults_to_reference_data_and_accepts_generated_data(self):
        self.assertEqual(PremierMock(None).accounts, ACCOUNTS)
        self.assertEqual(PremierMock(None).transactions, TRANSACTIONS)
        data = generate(42)
        seeded = PremierMock(None, data=data)
        self.assertEqual(seeded.accounts, data["accounts"])
        self.assertEqual(seeded.transactions, data["transactions"])


class Generated(unittest.TestCase):
    def test_same_seed_same_data(self):
        self.assertEqual(generate(123), generate(123))

    def test_different_seeds_differ(self):
        self.assertNotEqual(generate(1), generate(2))
        self.assertNotEqual(generate(1), generate(0))

    def test_does_not_use_global_random_state(self):
        with mock.patch("random.random", side_effect=AssertionError), \
                mock.patch("random.randint", side_effect=AssertionError):
            generate(7)

    def test_rejects_out_of_range_seed(self):
        for bad in (-1, 1_000_000, "5", 1.5, True):
            with self.assertRaises(ValueError):
                generate(bad)

    def test_invariants_hold_for_200_seeds(self):
        for seed in range(1, 201):
            with self.subTest(seed=seed):
                self._check(generate(seed))

    def _check(self, data):
        self.assertEqual(set(data), {"accounts", "transactions"})
        accounts, transactions = data["accounts"], data["transactions"]
        self.assertEqual(list(accounts), list(ACCOUNTS))
        self.assertEqual(list(transactions), list(TRANSACTIONS))
        for ident, account in accounts.items():
            reference = ACCOUNTS[ident]
            self.assertEqual(set(account), set(reference))
            self.assertEqual((account["type"], account["party"]), (reference["type"], reference["party"]))
            for key, value in account.items():
                self.assertIs(type(value), type(reference[key]), key)
            if account["type"] == "DDA":
                self.assertGreaterEqual(account["avail"], demo_data.MIN_DDA_CENTS)
                self.assertGreaterEqual(account["avail"], 2500)  # the README's USD 25 transfer fits
                self.assertLessEqual(account["avail"], account["ledger"])
                self.assertLessEqual(account["avail"], max(demo_data.MIN_DDA_CENTS, reference["avail"] * 4))
            else:
                self.assertGreater(account["next_total"], 0)
                self.assertGreaterEqual(account["past_due"], 0)
                self.assertEqual(account["pmt_due"], account["next_total"] + account["past_due"])
                self.assertGreaterEqual(account["payoff"], account["pmt_due"])
                self.assertLessEqual(account["payoff"], reference["payoff"] * 3)
                due = date.fromisoformat(account["next_date"])
                self.assertEqual(due.isoformat(), account["next_date"])
                self.assertGreater(due, LATEST)
        for ident, rows in transactions.items():
            self.assertEqual(accounts[ident]["type"], "DDA")
            self.assertGreater(len(rows), PAGE)  # a second history page always exists
            self.assertLessEqual(len(rows), demo_data.MAX_TRANSACTIONS)
            prefix = TRANSACTIONS[ident][0][0][:3]
            self.assertEqual(len({row[0] for row in rows}), len(rows))
            dates = []
            for row in rows:
                self.assertIsInstance(row, tuple)
                self.assertEqual(len(row), 5)
                trn_id, posted, direction, cents, description = row
                self.assertTrue(trn_id.startswith(prefix))
                self.assertEqual(date.fromisoformat(posted).isoformat(), posted)
                self.assertLessEqual(date.fromisoformat(posted), LATEST)
                self.assertIn(direction, {"Debit", "Credit"})
                self.assertIs(type(cents), int)
                self.assertGreater(cents, 0)
                names = demo_data.DEBIT_MERCHANTS if direction == "Debit" else demo_data.CREDIT_SOURCES
                self.assertIn(description, names)
                self.assertTrue(description.startswith("Fictional "))
                dates.append(posted)
            self.assertEqual(dates, sorted(dates, reverse=True))  # newest first, as in the reference


class Seeds(unittest.TestCase):
    def test_choose_seed_honours_demo_seed(self):
        self.assertEqual(choose_seed({"DEMO_SEED": "0"}), 0)
        self.assertEqual(choose_seed({"DEMO_SEED": "4711"}), 4711)
        self.assertEqual(choose_seed({"DEMO_SEED": " 999999 "}), 999999)

    def test_choose_seed_rejects_bad_values(self):
        for bad in ("", "abc", "-1", "1000000", "1.5", "1e3", "+5"):
            with self.subTest(value=bad), self.assertRaises(ValueError) as caught:
                choose_seed({"DEMO_SEED": bad})
            self.assertIn("DEMO_SEED", str(caught.exception))

    def test_choose_seed_draws_a_fresh_seed_otherwise(self):
        seeds = {choose_seed({}) for _ in range(200)}
        self.assertTrue(all(1 <= seed <= 999999 for seed in seeds))
        self.assertGreater(len(seeds), 1)

    def test_seed_line_wording(self):
        self.assertEqual(seed_line(4711),
                         "Demo data seed: 4711; set DEMO_SEED=4711 to get the same data again.")
        self.assertEqual(seed_line(0),
                         "Demo data seed: 0; set DEMO_SEED=0 to get the same data again."
                         " (reference data, as in the README's checked sequence)")


SEEDS = range(0, 201)


def replies(premier):
    """Every success reply the seeded data feeds: (definition, body), with every history page."""
    out = []
    for party in sorted({account["party"] for account in premier.accounts.values()}):
        out.append(("party", premier._party({"PartyAcctRelSel": {"PartyKeys": {"PartyId": party}}})))
    for ident, account in sorted(premier.accounts.items()):
        key = "dda" if account["type"] == "DDA" else "loan"
        out.append((key, premier._account({"AcctSel": {"AcctKeys": {"AcctId": ident, "AcctType": account["type"]}}}, key)))
    for ident in sorted(premier.transactions):
        body = {"AcctTrnSel": {"AcctKeys": {"AcctId": ident, "AcctType": "DDA"}}}
        while True:
            page = premier._transactions(body)
            out.append(("trn", page))
            cursor = page["RecCtrlOut"].get("Cursor")
            if cursor is None:
                break
            body = {**body, "RecCtrlIn": {"Cursor": cursor}}
    return out


def amounts(value):
    """Every Amt in a reply body."""
    if isinstance(value, dict):
        return [item for key, inner in value.items() for item in ([inner] if key == "Amt" else amounts(inner))]
    if isinstance(value, list):
        return [item for inner in value for item in amounts(inner)]
    return []


class SeededRepliesFitTheModels(unittest.TestCase):
    """Each reply is built through its generated model; vendor-free."""

    def test_every_seeded_reply_is_its_model_with_exact_decimal_amounts(self):
        for seed in SEEDS:
            for key, body in replies(PremierMock(None, data=generate(seed))):
                with self.subTest(seed=seed, definition=key):
                    self.assertIsNotNone(body)
                    self.assertEqual(plain(REPLY[key].model_validate(body)), body)
                    self.assertEqual(loads(dumps(body)), body)  # the wire carries exactly this
                    for amount in amounts(body):
                        self.assertIs(type(amount), Decimal)
                        self.assertEqual(amount.as_tuple().exponent, -2)

    def test_every_seeded_transaction_reaches_the_history_pages(self):
        for seed in (0, 42, 4711):
            data = generate(seed)
            pages = [body for key, body in replies(PremierMock(None, data=data)) if key == "trn"]
            sent = [(record["AcctTrnKeys"]["AcctTrnIdent"], record["AcctTrnInfo"]["TrnAmt"]["Amt"])
                    for page in pages for record in page["AcctTrnRec"]]
            expected = [(row[0], Decimal(row[3]) / 100) for ident in sorted(data["transactions"])
                        for row in data["transactions"][ident]]
            self.assertEqual(sent, expected)

    def test_reference_reply_amounts(self):
        body = PremierMock(None)._account({"AcctSel": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}}}, "dda")
        self.assertIn('"Amt":1250.00', dumps(body))

    def test_a_value_that_does_not_fit_the_model_fails_when_the_reply_is_built(self):
        data = generate(0)
        data["accounts"]["5550019001"]["next_date"] = "2026-02-30"  # not a date
        with self.assertRaises(ValidationError):
            PremierMock(None, data=data)._account(
                {"AcctSel": {"AcctKeys": {"AcctId": "5550019001", "AcctType": "LOAN"}}}, "loan")
        data = generate(0)
        data["accounts"]["5550010001"]["avail"] = 1250.0  # a float is never money
        with self.assertRaises(TypeError):
            PremierMock(None, data=data)._account(
                {"AcctSel": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}}}, "dda")


class SeededRepliesFitThePinnedDefinitions(unittest.TestCase):
    """The same replies against the pinned definitions' response schemas (needs the vendor files)."""

    def test_every_seeded_reply_validates_against_the_pinned_schemas(self):
        contract = load_contract()
        for seed in SEEDS:
            for key, body in replies(PremierMock(contract, data=generate(seed))):
                with self.subTest(seed=seed, definition=key):
                    contract.validate_response(key, 200, body)


if __name__ == "__main__":
    unittest.main()
