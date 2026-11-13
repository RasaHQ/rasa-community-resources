"""Seeded fictional demo data: reference seed, reproducibility and invariants. Vendor-free."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from contract_inputs import MissingContractInput, load_inputs
import demo_data
from demo_data import REFERENCE_SEED, choose_seed, generate, seed_line
from fixture_control import current, reset
from mock_server import FIXTURE, FixtureState, MockRefused, SymitarMock
from recorded_exchanges import EXCHANGES
from vendor_api import reply_body
from vendor_client import WireRequest

MONEY = re.compile(r"-?(?:0|[1-9][0-9]*)\.[0-9]{2}")


def shape(value):
    """Keys and value types, with lists reduced to their item shape."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.reference = json.loads(FIXTURE.read_bytes())

    def test_seed_zero_is_the_reference_data(self):
        self.assertEqual(REFERENCE_SEED, 0)
        data = generate(0)
        self.assertEqual(data, self.reference)
        self.assertEqual(json.dumps(data, sort_keys=True), json.dumps(self.reference, sort_keys=True))
        data["shares"][0]["available"] = "0.00"
        self.assertEqual(generate(0)["shares"][0]["available"], "1200.50")

    def test_same_seed_same_data_and_different_seeds_differ(self):
        self.assertEqual(generate(4242), generate(4242))
        self.assertNotEqual(generate(4242), generate(4243))
        self.assertNotEqual(generate(1), generate(0))

    def test_global_random_state_is_untouched(self):
        import random
        random.seed(99)
        expected = random.random()
        random.seed(99)
        generate(123)
        self.assertEqual(random.random(), expected)

    def test_rejects_invalid_seeds(self):
        for seed in (-1, 1_000_000, "1", 1.0, True, None):
            with self.subTest(seed=seed), self.assertRaises(ValueError):
                generate(seed)

    def test_invariants_hold_for_200_seeds(self):
        reference_shape = shape(self.reference)
        reference_date = date.fromisoformat(self.reference["payoff"]["reference_date"])
        latest = max(item["date"] for item in self.reference["transactions"])
        for seed in range(1, 201):
            data = generate(seed)
            with self.subTest(seed=seed):
                self.assertEqual(shape(data), reference_shape)
                for key in ("fixture", "institution", "account_number", "currency"):
                    self.assertEqual(data[key], self.reference[key])
                self.assertEqual(data["payoff"]["reference_date"], self.reference["payoff"]["reference_date"])
                self.assertEqual(data["payoff"]["max_days"], self.reference["payoff"]["max_days"])
                self.assertEqual([(s["alias"], s["id"]) for s in data["shares"]],
                                 [(s["alias"], s["id"]) for s in self.reference["shares"]])
                self.assertEqual([(l["alias"], l["id"]) for l in data["loans"]],
                                 [(l["alias"], l["id"]) for l in self.reference["loans"]])

                for share in data["shares"]:
                    self.assertRegex(share["balance"], MONEY)
                    self.assertRegex(share["available"], MONEY)
                    balance, available = Decimal(share["balance"]), Decimal(share["available"])
                    self.assertGreater(available, 0)
                    self.assertLessEqual(available, balance)
                    if share["alias"] == "checking":
                        self.assertTrue(150 <= balance <= 8000)
                        self.assertGreaterEqual(available, 100)  # room for the README's 1.25 transfer
                    else:
                        self.assertTrue(500 <= balance <= 30000)
                        self.assertEqual(available, balance)

                daily = data["payoff"]["daily_interest"]
                self.assertRegex(daily, MONEY)
                self.assertGreater(Decimal(daily), 0)
                for loan in data["loans"]:
                    money = {key: loan[key] for key in ("balance", "payment_due", "regular_payment", "minimum_payment", "past_due")}
                    for value in money.values():
                        self.assertRegex(value, MONEY)
                    balance, due, regular, minimum, past_due = (Decimal(money[key]) for key in
                        ("balance", "payment_due", "regular_payment", "minimum_payment", "past_due"))
                    self.assertTrue(1500 <= balance <= 15000)
                    self.assertTrue(150 <= regular <= 400)
                    self.assertTrue(5 <= past_due <= 90)
                    self.assertEqual(due, regular + past_due)
                    self.assertTrue(0 < minimum < regular)
                    self.assertGreaterEqual(balance, due)
                    self.assertEqual(len({due, regular, minimum, past_due}), 4)
                    self.assertGreater(date.fromisoformat(loan["due_date"]), reference_date)
                    payoff = balance + data["payoff"]["max_days"] * Decimal(daily)
                    self.assertGreaterEqual(payoff, balance)

                transactions = data["transactions"]
                self.assertEqual([item["sequence"] for item in transactions], list(range(1, len(transactions) + 1)))
                self.assertEqual([item["date"] for item in transactions], sorted(item["date"] for item in transactions))
                counts = {share["id"]: 0 for share in data["shares"]}
                for item in transactions:
                    counts[item["share_id"]] += 1
                    self.assertEqual(date.fromisoformat(item["date"]).isoformat(), item["date"])
                    self.assertLessEqual(item["date"], latest)
                    self.assertGreaterEqual(date.fromisoformat(item["date"]), date.fromisoformat(latest) - timedelta(days=20))
                    self.assertTrue(item["description"].startswith("Fictional "))
                    self.assertRegex(item["amount"], MONEY)
                    self.assertNotEqual(Decimal(item["amount"]), 0)
                    if item["share_id"] == "0002":
                        self.assertGreater(Decimal(item["amount"]), 0)
                self.assertTrue(21 <= counts["0001"] <= 26)  # more than the host's 20-row page
                self.assertTrue(3 <= counts["0002"] <= 6)
                self.assertTrue(any(Decimal(i["amount"]) > 0 for i in transactions if i["share_id"] == "0001"))


class SeedChoiceTests(unittest.TestCase):
    def test_demo_seed_is_honoured(self):
        self.assertEqual(choose_seed({"DEMO_SEED": "0"}), 0)
        self.assertEqual(choose_seed({"DEMO_SEED": " 42 "}), 42)
        self.assertEqual(choose_seed({"DEMO_SEED": "999999"}), 999999)

    def test_bad_values_are_refused_plainly(self):
        for value in ("", "-1", "1000000", "1.5", "abc", "0x10", "١"):
            with self.subTest(value=value), self.assertRaises(ValueError) as caught:
                choose_seed({"DEMO_SEED": value})
            self.assertIn("DEMO_SEED", str(caught.exception))

    def test_fresh_seed_without_demo_seed(self):
        seeds = {choose_seed({}) for _ in range(200)}
        self.assertTrue(all(type(seed) is int and 1 <= seed <= 999999 for seed in seeds))
        self.assertGreater(len(seeds), 1)

    def test_seed_line_wording(self):
        self.assertEqual(seed_line(48213), "Demo data seed: 48213; set DEMO_SEED=48213 to get the same data again.")
        self.assertEqual(seed_line(0), "Demo data seed: 0; set DEMO_SEED=0 to get the same data again."
                                       " (reference data, as in the README's checked sequence)")


class StoredSeedTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.path = self.root / "fixture.sqlite3"

    def test_default_state_is_reference_data(self):
        state = FixtureState(self.path, "epoch-1", initialize=True)
        try:
            self.assertEqual(state.seed, 0)
            self.assertEqual(state.snapshot(), (json.loads(FIXTURE.read_bytes()), 0))
        finally:
            state.close()

    def test_seed_is_stored_and_reused_on_reopen(self):
        FixtureState(self.path, "epoch-1", initialize=True, seed=777).close()
        state = FixtureState(self.path, "epoch-1", seed=5)  # seed is ignored when reopening
        try:
            self.assertEqual(state.seed, 777)
            self.assertEqual(state.snapshot(), (generate(777), 0))
        finally:
            state.close()

    def test_changed_fingerprint_or_seed_is_refused(self):
        FixtureState(self.path, "epoch-1", initialize=True, seed=777).close()
        connection = sqlite3.connect(self.path)
        connection.execute("UPDATE fixture SET seed=778")
        connection.commit()
        connection.close()
        with self.assertRaises(MockRefused):
            FixtureState(self.path, "epoch-1")
        with patch.object(demo_data, "data_hash", return_value="0" * 64):
            connection = sqlite3.connect(self.path)
            connection.execute("UPDATE fixture SET seed=777")
            connection.commit()
            connection.close()
            with self.assertRaises(MockRefused):
                FixtureState(self.path, "epoch-1")
        FixtureState(self.path, "epoch-1").close()

    def test_invalid_seed_is_refused_before_any_file(self):
        with self.assertRaises(MockRefused):
            FixtureState(self.path, "epoch-1", initialize=True, seed=-1)
        self.assertFalse(self.path.exists())

    def test_state_from_before_seeds_is_reference_data(self):
        FixtureState(self.path, "epoch-1", initialize=True).close()
        connection = sqlite3.connect(self.path)
        connection.execute("ALTER TABLE fixture DROP COLUMN seed")
        connection.commit()
        connection.close()
        state = FixtureState(self.path, "epoch-1")
        try:
            self.assertEqual(state.seed, 0)
        finally:
            state.close()

    def test_manifest_records_seed_at_creation_and_reset(self):
        root = self.root / "state"
        record = current(root, initialize=True, seed=31337)
        self.assertEqual(record["seed"], 31337)
        self.assertEqual(current(root)["seed"], 31337)
        new = reset(root, acknowledge=True, reason="new fictional exercise", seed=0)
        self.assertEqual(new["seed"], 0)
        audit = json.loads((root / new["audit"]).read_text())
        self.assertEqual((audit["old_seed"], audit["new_seed"]), (31337, 0))
        state = FixtureState(root / new["directory"] / "mock.sqlite3", new["epoch"])
        try:
            self.assertEqual(state.seed, 0)
        finally:
            state.close()


SEEDS = range(0, 201)
RECORDED = {operation: body for operation, side, status, media, body in EXCHANGES
            if side == "response" and status == 200}


def seeded_replies(data):
    """The recorded replies with every seeded value put in: (operation, body). Vendor-free."""
    out = []
    balances = deepcopy(RECORDED["findAccountByWithBalances"])
    shares = {share["id"]: share for share in data["shares"]}
    for item in balances["shares"]:
        item.update(balance=shares[item["shareId"]]["balance"], availableBalance=shares[item["shareId"]]["available"])
    out.append(("findAccountByWithBalances", balances))
    template = RECORDED["searchLoans"][0]
    out.append(("searchLoans", [{**deepcopy(template), "loanId": loan["id"], "nickname": loan["alias"],
                                 "balance": loan["balance"], "paymentDue": loan["payment_due"],
                                 "dueDate": loan["due_date"], "payment": loan["regular_payment"],
                                 "minimumPayment": loan["minimum_payment"], "pastDueAmount": loan["past_due"]}
                                for loan in data["loans"]]))
    row = RECORDED["searchAccountTransactions"]["transactions"][0]
    rows = [{**deepcopy(row), "postDate": item["date"], "description": item["description"],
             "amount": item["amount"], "sequenceNumber": item["sequence"]} for item in data["transactions"]]
    out.append(("searchAccountTransactions",
                {"transactions": rows, "paging": {"nextOffset": "", "results": len(rows), "total": len(rows)}}))
    reference = date.fromisoformat(data["payoff"]["reference_date"])
    for loan in data["loans"]:
        for days in range(data["payoff"]["max_days"] + 1):
            amount = Decimal(loan["balance"]) + days * Decimal(data["payoff"]["daily_interest"])
            out.append(("calculateLoanPayoffQuote", {**RECORDED["calculateLoanPayoffQuote"],
                                                     "payoffDate": (reference + timedelta(days=days)).isoformat(),
                                                     "totalPayoffAmount": format(amount, ".2f")}))
    return out


class SeededRepliesFitTheModels(unittest.TestCase):
    """Every seeded value fits the generated reply models; vendor-free."""

    def test_every_seeded_reply_is_its_model_unchanged(self):
        for seed in SEEDS:
            for operation, body in seeded_replies(generate(seed)):
                with self.subTest(seed=seed, operation=operation):
                    self.assertEqual(reply_body(operation, body), body)

    def test_amounts_are_exact_decimals_never_floats(self):
        source = Path(demo_data.__file__).read_text()
        for banned in ("float(", "lognormvariate", "uniform("):
            self.assertNotIn(banned, source)
        for seed in (1, 42, 4242):
            text = json.dumps(generate(seed))
            data = json.loads(text, parse_float=lambda raw: self.fail("a float in the demo data: " + raw))
            for value in [s[k] for s in data["shares"] for k in ("balance", "available")] + \
                         [l[k] for l in data["loans"] for k in ("balance", "payment_due", "regular_payment",
                                                                "minimum_payment", "past_due")] + \
                         [t["amount"] for t in data["transactions"]] + [data["payoff"]["daily_interest"]]:
                self.assertEqual(Decimal(value).as_tuple().exponent, -2)

    def test_a_value_that_does_not_fit_the_model_fails_when_the_reply_is_built(self):
        from pydantic import ValidationError
        operation, body = seeded_replies(generate(0))[0]
        body["shares"][0]["balance"] = 1250.5  # the files declare a string amount
        with self.assertRaises(ValidationError):
            reply_body(operation, body)


class SeededRepliesFitThePinnedFiles(unittest.TestCase):
    """The mock's own replies for many seeds, validated against the pinned files (needs the vendor files)."""

    def test_every_seeded_reply_validates_against_the_pinned_files(self):
        try:
            inputs = load_inputs()
        except MissingContractInput as error:
            self.skipTest(str(error))
        number = "0000000001"
        mock = None
        with tempfile.TemporaryDirectory() as folder:
            for seed in SEEDS:
                state = FixtureState(Path(folder).resolve() / f"seed-{seed}.sqlite3", "epoch-1", initialize=True, seed=seed)
                try:
                    if mock is None:
                        mock = SymitarMock(inputs, state)
                    else:
                        mock.state = state  # reading the pinned files once keeps 200 seeds quick
                    data, _ = state.snapshot()
                    reference = date.fromisoformat(data["payoff"]["reference_date"])
                    requests = [("findAccountBy", {"accountNumber": number}),
                                ("findAccountByWithBalances", {"accountNumber": number}),
                                ("searchLoans", {"accountNumber": number})]
                    for share in data["shares"]:
                        for offset in ("0", "20"):
                            requests.append(("searchAccountTransactions", {
                                "accountNumber": number, "shareId": share["id"], "startDate": "2026-10-01",
                                "endDate": "2026-11-12", "count": 20, "offset": offset}))
                    for loan in data["loans"]:
                        for days in (0, 15, data["payoff"]["max_days"]):
                            requests.append(("calculateLoanPayoffQuote", {
                                "accountNumber": number, "loanId": loan["id"],
                                "payoffDate": (reference + timedelta(days=days)).isoformat()}))
                    requests.append(("postTransfer", {"donor": {"accountNumber": number, "shareId": "0001"},
                                                      "recipient": {"accountNumber": number, "shareId": "0002"},
                                                      "amount": "1.25"}))
                    for operation, body in requests:
                        with self.subTest(seed=seed, operation=operation, body=body):
                            path = mock.contract.request(operation, body).replace("{InstitutionUniversalId}",
                                                                                  data["institution"])
                            response = mock.send(WireRequest("POST", path, json.dumps(body).encode()))
                            self.assertEqual(response.status, 200)
                            reply = json.loads(response.body)
                            mock.contract.response(operation, 200, response.media_type, reply)
                            self.assertEqual(reply_body(operation, reply), reply)
                finally:
                    state.close()


if __name__ == "__main__":
    unittest.main()
