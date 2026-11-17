"""Typed calls through the native MCP client, with a private stdio child."""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
import json

from .models import Basket, Order, PlaceOrder
from .operations import Catalog, Empty, Lookup, OrderResult, QuoteResult


class ShopClient:
    def __init__(self, command, *, arguments, environment, directory):
        self.command, self.arguments, self.environment, self.directory = command, arguments, environment, directory
        self.stack, self.session = None, None

    async def __aenter__(self):
        from .locked_versions import require_locked_version
        require_locked_version(self.directory, "mcp")
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        self.stack = AsyncExitStack()
        try:
            parameters = StdioServerParameters(command=self.command, args=self.arguments,
                env=self.environment, cwd=str(self.directory))
            reader, writer = await self.stack.enter_async_context(stdio_client(parameters))
            self.session = await self.stack.enter_async_context(ClientSession(reader, writer))
            async with asyncio.timeout(30):
                await self.session.initialize()
                tools = await self.session.list_tools()
            if {tool.name for tool in tools.tools} != {"shop_catalog", "shop_quote", "shop_place", "shop_lookup"}:
                raise RuntimeError("The shop tool list has changed")
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *error):
        self.session = None
        if self.stack:
            await self.stack.aclose()

    async def call(self, name, request, result_model):
        if self.session is None:
            raise RuntimeError("The shop connection is not open")
        async with asyncio.timeout(30):
            reply = await self.session.call_tool(name, request.model_dump(mode="json"))
        if reply.isError or len(reply.content) != 1 or reply.content[0].type != "text":
            raise RuntimeError("The shop did not return a complete result")
        try:
            payload = json.loads(reply.content[0].text)
            structured = getattr(reply, "structuredContent", None)
            if structured is not None and structured != payload:
                raise ValueError("Two result representations disagree")
            if type(payload) is not dict or payload.get("success") is not True:
                raise ValueError("The operation did not complete")
            return result_model.model_validate_json(json.dumps(payload["data"], allow_nan=False))
        except Exception:
            raise RuntimeError("The shop result could not be validated") from None

    async def catalog(self):
        return await self.call("shop_catalog", Empty(), Catalog)

    async def quote(self, basket: Basket):
        return (await self.call("shop_quote", basket, QuoteResult)).quote

    async def place(self, reference, request_key):
        request = PlaceOrder(quote_reference=reference, request_key=request_key)
        order = (await self.call("shop_place", request, OrderResult)).order
        if order.quote.reference != reference or order.request_key != request_key:
            raise RuntimeError("The original order response changed")
        return order

    async def lookup(self, number):
        request = Lookup.model_validate_json(json.dumps({"number": str(number)}))
        order = (await self.call("shop_lookup", request, OrderResult)).order
        if order.number != request.number:
            raise RuntimeError("The order response changed")
        return order
