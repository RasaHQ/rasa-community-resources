"""Typed shop operations registered once with the Core MCP adapter."""
from __future__ import annotations

import asyncio
from uuid import UUID

from .models import Basket, BasketItem, Order, PlaceOrder, Product, Quote, Record
from .shop import ShopError


class Empty(Record):
    pass


class Catalog(Record):
    currency: str
    products: tuple[Product, ...]


class QuoteResult(Record):
    quote: Quote


class OrderResult(Record):
    order: Order


class Lookup(Record):
    number: UUID


class BasketInput(Record):
    items: list[BasketItem]


class PlaceInput(Record):
    quote_reference: str
    request_key: str


class LookupInput(Record):
    number: str


async def safe_call(function, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except ShopError:
        raise
    except Exception:
        raise ShopError("SHOP_UNAVAILABLE") from None


def create_shop_server(shop):
    # Imports and server creation are explicit startup actions. Unit tests of
    # the shop need neither the MCP SDK nor a provider credential.
    from zeo_core.adapters.mcp import create_server
    from zeo_core.core.registry import OperationRegistry

    registry = OperationRegistry()

    async def catalog(request: Empty):
        return Catalog(currency=shop.currency, products=tuple(await safe_call(shop.catalog))).model_dump(mode="json")

    async def quote(request: BasketInput):
        basket = Basket.model_validate_json(request.model_dump_json())
        return QuoteResult(quote=await safe_call(shop.quote, basket)).model_dump(mode="json")

    async def place(request: PlaceInput):
        placement = PlaceOrder.model_validate_json(request.model_dump_json())
        return OrderResult(order=await safe_call(shop.place, placement)).model_dump(mode="json")

    async def lookup(request: LookupInput):
        number = Lookup.model_validate_json(request.model_dump_json()).number
        return OrderResult(order=await safe_call(shop.lookup, number)).model_dump(mode="json")

    # The adapter accepts JSON dictionaries. Validate typed responses above and
    # serialize in JSON mode before registry serialization (UUID/date included).
    registry.register("shop_catalog", catalog, Empty, description="Read the product catalog and available quantities.")
    registry.register("shop_quote", quote, BasketInput, description="Price a basket without placing an order.")
    registry.register("shop_place", place, PlaceInput, description="Place the exact reviewed quote once.")
    registry.register("shop_lookup", lookup, LookupInput, description="Read the current state of an order.")
    return create_server(registry, name="shop-assistant")
