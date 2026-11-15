"""Offline shop behavior with a spreadsheet double and a real local journal."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from shop_demo.models import Basket, BasketItem, PlaceOrder, review
from shop_demo.sheets import ORDER_HEADERS, PRODUCT_HEADERS, SheetFailure, orders
from shop_demo.shop import Shop, ShopError


class MemoryTables:
    def __init__(self):
        self.rows = {"Products": [PRODUCT_HEADERS[:], ["NOTEBOOK", "Notebook", 12900, 12],
                                  ["MARKER", "Marker set", 4500, 8]], "Orders": [ORDER_HEADERS[:]]}
        self.append_calls = 0
        self.fail_before = self.fail_after = False

    def read(self, tab):
        return [row[:] for row in self.rows[tab]]

    def append(self, tab, row):
        self.append_calls += 1
        if self.fail_before:
            raise TimeoutError("synthetic")
        self.rows[tab].append(row[:])
        if self.fail_after:
            raise TimeoutError("synthetic")


class ShopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "orders.sqlite3"
        self.now = datetime(2026, 11, 16, 10, tzinfo=timezone.utc)
        self.tables = MemoryTables()
        self.shop = Shop(self.tables, journal=self.path, currency="MXN", clock=lambda: self.now)

    def tearDown(self):
        self.shop.close()
        self.tmp.cleanup()

    def basket(self, count=2):
        return Basket(items=(BasketItem(code="NOTEBOOK", quantity=count),))

    def request(self, quote, key="telegram:101"):
        return PlaceOrder(quote_reference=quote.reference, request_key=key)

    def test_quote_and_confirm_record_exact_total_and_replay_does_not_append(self):
        quote = self.shop.quote(self.basket())
        self.assertEqual(quote.total_cents, 25800)
        self.assertIn("MXN 258.00", review(quote))
        self.assertEqual(self.tables.append_calls, 0)
        order = self.shop.place(self.request(quote))
        self.assertEqual(order.status, "placed")
        self.assertEqual(self.shop.place(self.request(quote)), order)
        self.assertEqual(self.tables.append_calls, 1)
        self.assertEqual(self.shop.catalog()[0].stock, 10)
        self.assertEqual(self.shop.lookup(order.number), order)

    def test_unknown_after_append_is_recovered_by_read_without_resend(self):
        quote = self.shop.quote(self.basket())
        self.tables.fail_after = True
        with self.assertRaisesRegex(ShopError, "ORDER_WRITE_HELD"):
            self.shop.place(self.request(quote))
        order = self.shop.place(self.request(quote))
        self.assertEqual(order.quote, quote)
        self.assertEqual(self.tables.append_calls, 1)
        with self.assertRaisesRegex(ShopError, "QUOTE_ALREADY_SUBMITTED"):
            self.shop.place(self.request(quote, "telegram:102"))

    def test_unknown_before_append_never_turns_into_a_fresh_append(self):
        quote = self.shop.quote(self.basket())
        self.tables.fail_before = True
        with self.assertRaisesRegex(ShopError, "ORDER_WRITE_HELD"):
            self.shop.place(self.request(quote))
        self.tables.fail_before = False
        with self.assertRaisesRegex(ShopError, "NEEDS_INSPECTION"):
            self.shop.place(self.request(quote))
        self.assertEqual(self.tables.append_calls, 1)
        with self.assertRaisesRegex(ShopError, "QUOTE_ALREADY_SUBMITTED"):
            self.shop.place(self.request(quote, "telegram:102"))

    def test_expired_or_changed_price_is_not_submitted(self):
        quote = self.shop.quote(self.basket())
        self.tables.rows["Products"][1][2] = 13000
        with self.assertRaisesRegex(ShopError, "QUOTE_CHANGED"):
            self.shop.place(self.request(quote))
        self.tables.rows["Products"][1][2] = 12900
        self.now += timedelta(minutes=6)
        with self.assertRaisesRegex(ShopError, "QUOTE_EXPIRED"):
            self.shop.place(self.request(quote))
        self.assertEqual(self.tables.append_calls, 0)

    def test_other_orders_reduce_available_stock_before_placement(self):
        first = self.shop.quote(self.basket(10))
        second = self.shop.quote(self.basket(5))
        self.shop.place(self.request(first))
        with self.assertRaisesRegex(ShopError, "QUOTE_CHANGED"):
            self.shop.place(self.request(second, "telegram:102"))
        self.assertEqual(self.tables.append_calls, 1)
        with self.assertRaisesRegex(ShopError, "OUT_OF_STOCK"):
            self.shop.quote(self.basket(3))

    def test_changed_request_key_or_record_refuses(self):
        first, second = self.shop.quote(self.basket()), self.shop.quote(self.basket(1))
        self.shop.place(self.request(first))
        with self.assertRaisesRegex(ShopError, "REQUEST_KEY_CHANGED"):
            self.shop.place(self.request(second))
        self.tables.rows["Orders"][1][2] += 1
        with self.assertRaises(SheetFailure):
            orders(self.tables)
        self.assertEqual(self.tables.append_calls, 1)

    def test_restart_reads_original_and_shipped_status(self):
        quote = self.shop.quote(self.basket())
        order = self.shop.place(self.request(quote))
        self.shop.close()
        self.tables.rows["Orders"][1][4] = "shipped"
        self.shop = Shop(self.tables, journal=self.path, currency="MXN", clock=lambda: self.now)
        replay = self.shop.place(self.request(quote))
        self.assertEqual(replay.number, order.number)
        self.assertEqual(replay.status, "shipped")
        self.assertEqual(self.tables.append_calls, 1)

    def test_closed_inputs_and_headers_refuse(self):
        for payload in [{"items": [{"code": "NOTEBOOK", "quantity": True}]},
                        {"items": [{"code": "NOTEBOOK", "quantity": 1, "price_cents": 1}]},
                        {"items": [{"code": "NOTEBOOK", "quantity": 1}] * 2}]:
            with self.assertRaises(ValidationError):
                Basket.model_validate_json(__import__("json").dumps(payload))
        self.tables.rows["Products"][0][2] = "Price"
        with self.assertRaises(SheetFailure):
            self.shop.catalog()
