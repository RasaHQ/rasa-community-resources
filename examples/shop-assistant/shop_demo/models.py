"""The public inputs and records for the shop example."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Product(Record):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{0,19}$")
    name: str = Field(min_length=1, max_length=80)
    price_cents: int = Field(ge=0, le=10_000_000)
    stock: int = Field(ge=0, le=100_000)


class BasketItem(Record):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{0,19}$")
    quantity: int = Field(ge=1, le=25)


class Basket(Record):
    items: tuple[BasketItem, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_codes(self):
        if len({item.code for item in self.items}) != len(self.items):
            raise ValueError("Use one line per product")
        return self


class PricedItem(Record):
    product: Product
    quantity: int = Field(ge=1, le=25)


class Quote(Record):
    reference: UUID
    items: tuple[PricedItem, ...] = Field(min_length=1, max_length=10)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    expires_at: datetime

    @model_validator(mode="after")
    def expiry_is_aware(self):
        if self.expires_at.tzinfo is None:
            raise ValueError("An explicit time zone is required")
        return self

    @property
    def total_cents(self):
        return sum(item.product.price_cents * item.quantity for item in self.items)


class Order(Record):
    number: UUID
    quote: Quote
    status: Literal["placed", "shipped"]
    created_at: datetime
    request_key: str = Field(min_length=1, max_length=120)


class PlaceOrder(Record):
    quote_reference: UUID
    request_key: str = Field(pattern=r"^[A-Za-z0-9:_-]{1,120}$")


def money(cents: int, currency: str):
    if type(cents) is not int or cents < 0:
        raise ValueError("An exact nonnegative cent amount is required")
    return f"{currency} {cents // 100}.{cents % 100:02d}"


def review(quote: Quote):
    lines = ["Please review this order:"]
    lines.extend(f"{item.quantity} x {item.product.name}: {money(item.product.price_cents * item.quantity, quote.currency)}"
                 for item in quote.items)
    lines.append(f"Total: {money(quote.total_cents, quote.currency)}")
    lines.append("Reply confirm in your next message to place it. Any other reply cancels this review.")
    return "\n".join(lines)
