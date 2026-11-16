"""A single-process shop: quote, explicit placement, and spreadsheet readback."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import threading
from uuid import UUID, uuid4

from .models import Basket, Order, PlaceOrder, PricedItem, Quote
from .sheets import Tables, order_row, orders, products
from .state import open_state


class ShopError(RuntimeError):
    """A fixed public reason, without provider errors or credentials."""


class Shop:
    def __init__(self, tables: Tables, *, journal: Path, currency: str, clock):
        self.tables, self.currency, self.clock = tables, currency, clock
        self.lock = threading.RLock()
        self.db = open_state(journal)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS basket_quotes (reference TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS placements (request_key TEXT PRIMARY KEY,
                quote_reference TEXT UNIQUE NOT NULL, body TEXT NOT NULL, phase TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def catalog(self):
        catalog, placed = products(self.tables), orders(self.tables)
        used = {}
        for order in placed:
            for line in order.quote.items:
                used[line.product.code] = used.get(line.product.code, 0) + line.quantity
        return [product.model_copy(update={"stock": max(0, product.stock - used.get(product.code, 0))})
                for product in catalog]

    def quote(self, basket: Basket):
        basket = Basket.model_validate(basket)
        with self.lock:
            catalog = {product.code: product for product in self.catalog()}
            items = []
            for item in basket.items:
                product = catalog.get(item.code)
                if product is None:
                    raise ShopError("UNKNOWN_PRODUCT")
                if item.quantity > product.stock:
                    raise ShopError("OUT_OF_STOCK")
                items.append(PricedItem(product=product, quantity=item.quantity))
            quote = Quote(reference=uuid4(), items=tuple(items), currency=self.currency,
                          expires_at=self.clock() + timedelta(minutes=5))
            self.db.execute("INSERT INTO basket_quotes VALUES(?,?)", (str(quote.reference), quote.model_dump_json()))
            return quote

    def place(self, request: PlaceOrder):
        request = PlaceOrder.model_validate(request)
        with self.lock:
            previous = self.db.execute("SELECT quote_reference,body,phase FROM placements WHERE request_key=?",
                                       (request.request_key,)).fetchone()
            if previous:
                if previous[0] != str(request.quote_reference):
                    raise ShopError("REQUEST_KEY_CHANGED")
                return self._read_original(request, previous[1])
            if self.db.execute("SELECT 1 FROM placements WHERE quote_reference=?", (str(request.quote_reference),)).fetchone():
                raise ShopError("QUOTE_ALREADY_SUBMITTED")
            row = self.db.execute("SELECT body FROM basket_quotes WHERE reference=?", (str(request.quote_reference),)).fetchone()
            if row is None:
                raise ShopError("QUOTE_NOT_FOUND")
            quote = Quote.model_validate_json(row[0])
            if self.clock() >= quote.expires_at:
                raise ShopError("QUOTE_EXPIRED")
            current = {product.code: product for product in self.catalog()}
            for item in quote.items:
                product = current.get(item.product.code)
                if product is None or product.price_cents != item.product.price_cents or product.name != item.product.name or product.stock < item.quantity:
                    raise ShopError("QUOTE_CHANGED")
            order = Order(number=uuid4(), quote=quote, status="placed", created_at=self.clock(), request_key=request.request_key)
            # Commit the original intent before any external write. A lost reply
            # leaves a retained original; it never permits another append.
            self.db.execute("INSERT INTO placements VALUES(?,?,?,'started')",
                (request.request_key, str(quote.reference), order.model_dump_json()))
            try:
                self.tables.append("Orders", order_row(order))
                return self._read_original(request, order.model_dump_json())
            except Exception:
                self.db.execute("UPDATE placements SET phase='held' WHERE request_key=?", (request.request_key,))
                raise ShopError("ORDER_WRITE_HELD") from None

    def _read_original(self, request, original_json):
        original = Order.model_validate_json(original_json)
        matches = [order for order in orders(self.tables) if order.request_key == request.request_key]
        if len(matches) != 1 or matches[0].model_copy(update={"status": "placed"}) != original:
            raise ShopError("ORIGINAL_ORDER_NEEDS_INSPECTION")
        self.db.execute("UPDATE placements SET phase='recorded' WHERE request_key=?", (request.request_key,))
        return matches[0]

    def lookup(self, number: UUID):
        matches = [order for order in orders(self.tables) if order.number == number]
        if len(matches) != 1:
            raise ShopError("ORDER_NOT_FOUND")
        return matches[0]
