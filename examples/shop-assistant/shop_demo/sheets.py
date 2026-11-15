"""Small table boundary; the live adapter delegates to the maintained Sheets service."""
from __future__ import annotations

import json
from typing import Protocol

from .models import Order, Product
from .table_schema import PRODUCT_COLUMNS, ORDER_COLUMNS

PRODUCT_HEADERS = list(PRODUCT_COLUMNS)
ORDER_HEADERS = list(ORDER_COLUMNS)


class SheetFailure(RuntimeError):
    pass


class Tables(Protocol):
    def read(self, tab: str) -> list[list]: ...
    def append(self, tab: str, row: list) -> None: ...


def integer(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit() and str(int(value)) == value:
        return int(value)
    raise SheetFailure("An integer table cell is invalid")


def checked_rows(tables: Tables, tab, header):
    rows = tables.read(tab)
    if not rows or rows[0] != header:
        raise SheetFailure(f"{tab} headers do not match the example")
    rows = [row for row in rows[1:] if any(str(cell) for cell in row)]
    if len(rows) > 200:
        raise SheetFailure("This demonstration is limited to 200 rows per table")
    return rows


def products(tables: Tables):
    found = []
    for row in checked_rows(tables, "Products", PRODUCT_HEADERS):
        if len(row) != 4:
            raise SheetFailure("A product row is incomplete")
        found.append(Product(code=row[0], name=row[1], price_cents=integer(row[2]), stock=integer(row[3])))
    if len({p.code for p in found}) != len(found):
        raise SheetFailure("Product codes must be unique")
    return found


def orders(tables: Tables):
    found = []
    for row in checked_rows(tables, "Orders", ORDER_HEADERS):
        if len(row) != 7:
            raise SheetFailure("An order row is incomplete")
        # JSON-mode validation admits the UUID/time wire representations while
        # retaining strict numeric, closed-record and enum checks.
        order = Order.model_validate_json(json.dumps({"number": row[0], "quote": json.loads(row[1]),
            "status": row[4], "created_at": row[5], "request_key": row[6]}))
        if integer(row[2]) != order.quote.total_cents or row[3] != order.quote.currency:
            raise SheetFailure("An order total does not match its recorded quote")
        found.append(order)
    if len({o.number for o in found}) != len(found) or len({o.request_key for o in found}) != len(found):
        raise SheetFailure("Order numbers and request keys must be unique")
    return found


def order_row(order: Order):
    return [str(order.number), order.quote.model_dump_json(), order.quote.total_cents, order.quote.currency,
            order.status, order.created_at.isoformat(), order.request_key]
