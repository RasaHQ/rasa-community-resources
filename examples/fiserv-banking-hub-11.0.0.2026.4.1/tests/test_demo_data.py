"""Seeded demo data: seed 0 is the reference set; other seeds vary but keep every invariant."""
from datetime import date
from decimal import Decimal
import unittest

from pydantic import ValidationError

from bh_demo import demo_data
from bh_demo.demo_data import REFERENCE_SEED, choose_seed, generate, seed_line
from bh_demo.mock import ACCOUNTS, BankingHubMock
from bh_demo.vendor_api import REPLY, dumps, loads, plain
from tests.support import load_contract


class DemoDataTests(unittest.TestCase):
    def test_reference_seed_is_the_reference_data(self):
        self.assertEqual(REFERENCE_SEED, 0)
        data = generate(0)
        self.assertEqual(data, ACCOUNTS)
        data["5550010001"]["avail"] = 1  # a copy: changing it leaves the reference alone
        self.assertEqual(ACCOUNTS["5550010001"]["avail"], 125000)

    def test_same_seed_same_data(self):
        for seed in (1, 42, 999_999):
            self.assertEqual(generate(seed), generate(seed))

    def test_different_seeds_differ(self):
        self.assertNotEqual(generate(1), generate(2))
        self.assertNotEqual(generate(1), ACCOUNTS)

    def test_does_not_touch_global_random_state(self):
        import random
        random.seed(7)
        expected = random.random()
        random.seed(7)
        generate(123)
        self.assertEqual(random.random(), expected)

    def test_invariants_hold_for_200_seeds(self):
        for seed in range(1, 201):
            data = generate(seed)
            self.assertEqual(sorted(data), sorted(ACCOUNTS))
            for ident, account in data.items():
                ref = ACCOUNTS[ident]
                with self.subTest(seed=seed, account=ident):
                    self.assertEqual(set(account), set(ref))
                    self.assertEqual((account["type"], account["party"]), (ref["type"], ref["party"]))
                    for key, value in account.items():
                        self.assertIs(type(value), type(ref[key]))
                    if account["type"] in {"DDA", "SDA"}:
                        low, high = demo_data.DEPOSIT_AVAIL_RANGE[account["type"]]
                        self.assertTrue(low <= account["avail"] <= high)
                        self.assertLessEqual(account["avail"], account["ledger"])
                        if account["type"] == "SDA":
                            self.assertEqual(account["avail"], account["ledger"])
                        else:
                            self.assertLessEqual(account["ledger"] - account["avail"], demo_data.PENDING_RANGE[1])
                    else:
                        self.assertTrue(demo_data.PRINCIPAL_RANGE[0] <= account["principal"]
                                        <= demo_data.PRINCIPAL_RANGE[1])
                        self.assertTrue(demo_data.INTEREST_RANGE[0] <= account["interest"]
                                        <= min(demo_data.INTEREST_RANGE[1], account["principal"]))
                        self.assertEqual(account["total"], account["principal"] + account["interest"])
                        due = date.fromisoformat(account["next_date"])
                        self.assertEqual(due.isoformat(), account["next_date"])
                        self.assertLessEqual(abs((due - date.fromisoformat(ref["next_date"])).days),
                                             demo_data.DUE_DATE_SHIFT_DAYS)

    def test_bad_seed_for_generate(self):
        for bad in (-1, 1_000_000, "1", 1.0, True):
            with self.assertRaises(ValueError):
                generate(bad)

    def test_choose_seed_honours_demo_seed(self):
        self.assertEqual(choose_seed({"DEMO_SEED": "0"}), 0)
        self.assertEqual(choose_seed({"DEMO_SEED": "123456"}), 123456)
        self.assertEqual(choose_seed({"DEMO_SEED": "999999"}), 999999)
        self.assertEqual(choose_seed({"DEMO_SEED": " 17 "}), 17)

    def test_choose_seed_rejects_bad_values(self):
        for bad in ("", "abc", "-1", "1000000", "1.5", "1e3", "٣"):
            with self.subTest(value=bad), self.assertRaises(ValueError) as caught:
                choose_seed({"DEMO_SEED": bad})
            self.assertIn("DEMO_SEED", str(caught.exception))

    def test_choose_seed_draws_without_demo_seed(self):
        seeds = {choose_seed({}) for _ in range(200)}
        self.assertTrue(all(isinstance(s, int) and 1 <= s <= 999_999 for s in seeds))
        self.assertGreater(len(seeds), 1)

    def test_seed_line_wording(self):
        self.assertEqual(seed_line(42), "Demo data seed: 42; set DEMO_SEED=42 to get the same data again.")
        self.assertEqual(seed_line(0), "Demo data seed: 0; set DEMO_SEED=0 to get the same data again."
                                       " (reference data, as in the README's checked sequence)")


class WiringTests(unittest.TestCase):
    def test_mock_defaults_to_reference_data(self):
        self.assertEqual(BankingHubMock(None).accounts, ACCOUNTS)
        self.assertEqual(BankingHubMock(None, data=generate(5)).accounts, generate(5))

    def _launch(self, environ):
        import contextlib
        import io
        import os
        from pathlib import Path
        from unittest import mock
        from bh_demo import launcher
        from bh_demo.contract import MissingContractInput
        output = io.StringIO()
        with mock.patch.dict(os.environ, environ), \
                mock.patch.object(launcher.BankingHubContract, "from_path",
                                  side_effect=MissingContractInput("vendor file absent")), \
                mock.patch("sys.argv", ["run_demo.py"]), contextlib.redirect_stdout(output):
            code = launcher.main(Path(__file__).resolve().parents[1])
        return code, output.getvalue().splitlines()

    def test_launcher_prints_the_seed_first(self):
        code, lines = self._launch({"DEMO_SEED": "0"})
        self.assertEqual(code, 2)
        self.assertEqual(lines[0], seed_line(0))
        self.assertTrue(lines[1].startswith("Not ready."))

    def test_launcher_refuses_a_bad_seed(self):
        code, lines = self._launch({"DEMO_SEED": "seven"})
        self.assertEqual(code, 2)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("Not ready. DEMO_SEED must be a whole number"))


SEEDS = range(0, 201)


def replies(mock):
    """Every success reply the seeded data feeds: (operation, body) for each party and account."""
    out = []
    for party in sorted({account["party"] for account in mock.accounts.values()}):
        out.append(("party", mock._party({"PartyAcctRelSel": {"PartyKeys": {"PartyId": party}}})))
    for ident, account in sorted(mock.accounts.items()):
        out.append(("acct", mock._account({"AcctSel": {"AcctKeys": {"AcctId": ident, "AcctType": account["type"]}}})))
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
            data = generate(seed)
            for operation, (code, body) in replies(BankingHubMock(None, data=data)):
                with self.subTest(seed=seed, operation=operation):
                    self.assertEqual(code, 200)
                    self.assertEqual(plain(REPLY[operation].model_validate(body)), body)
                    self.assertEqual(loads(dumps(body)), body)  # the wire carries exactly this
                    for amount in amounts(body):
                        self.assertIs(type(amount), Decimal)
                        self.assertEqual(amount.as_tuple().exponent, -2)

    def test_reply_amounts_are_the_seeded_cents(self):
        for seed in (0, 7, 4821):
            data = generate(seed)
            mock = BankingHubMock(None, data=data)
            _, body = mock._account({"AcctSel": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}}})
            shown = {row["BalType"]: row["CurAmt"]["Amt"] for row in body["AcctRec"]["DepositAcctInfo"]["AcctBal"]}
            self.assertEqual(shown, {"Ledger": Decimal(data["5550010001"]["ledger"]) / 100,
                                     "Avail": Decimal(data["5550010001"]["avail"]) / 100})
        _, body = BankingHubMock(None)._account({"AcctSel": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}}})
        self.assertIn('"Amt":1250.00', dumps(body))

    def test_a_value_that_does_not_fit_the_model_fails_when_the_reply_is_built(self):
        data = generate(0)
        data["5550019001"]["next_date"] = "2026-02-30"  # not a date
        with self.assertRaises(ValidationError):
            BankingHubMock(None, data=data)._account(
                {"AcctSel": {"AcctKeys": {"AcctId": "5550019001", "AcctType": "LOAN"}}})
        data = generate(0)
        data["5550010001"]["avail"] = 1250.0  # a float is never money
        with self.assertRaises(TypeError):
            BankingHubMock(None, data=data)._account(
                {"AcctSel": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}}})


class SeededRepliesFitThePinnedRelease(unittest.TestCase):
    """The same replies against the pinned release's response schemas (needs the vendor files)."""

    def test_every_seeded_reply_validates_against_the_pinned_schemas(self):
        contract = load_contract()
        for seed in SEEDS:
            for operation, (code, body) in replies(BankingHubMock(contract, data=generate(seed))):
                with self.subTest(seed=seed, operation=operation):
                    contract.validate_response(operation, code, body)


if __name__ == "__main__":
    unittest.main()
