"""Native Mantle conversation; only read and quote tools are given to the model."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
import json
import os
from pathlib import Path
from uuid import uuid4

from pydantic import Field

from .models import Basket, Order, Quote, Record, money
from .operations import Catalog


class TurnView(Record):
    # This runtime record is mutable only while its owning native turn is open.
    model_config = {**Record.model_config, "frozen": False}
    active: bool = True
    latest_order: str | None
    quote: Quote | None = None
    catalog: Catalog | None = None
    order: Order | None = None
    note: str | None = None
    calls: int = Field(default=0, ge=0)


_view = ContextVar("shop_turn", default=None)
_bridge = None


def bridge():
    view = _view.get()
    if _bridge is None or view is None or not view.active or view.calls >= 8:
        raise RuntimeError("There is no active shop turn")
    view.calls += 1
    return _bridge, view


async def catalog_tool():
    client, view = bridge()
    view.catalog = await client.catalog()
    return view.catalog.model_dump(mode="json")


async def basket_tool(items):
    client, view = bridge()
    if view.quote is not None:
        raise ValueError("Only one basket review may be prepared per message")
    basket = Basket.model_validate_json(json.dumps({"items": items}, allow_nan=False))
    view.quote = await client.quote(basket)
    return view.quote.model_dump(mode="json")


async def order_tool():
    client, view = bridge()
    if view.latest_order is None:
        view.note = "No order has been placed in this conversation."
        return {"message": view.note}
    view.order = await client.lookup(view.latest_order)
    return view.order.model_dump(mode="json")


async def clarify_tool(missing):
    _, view = bridge()
    questions = {"product": "Which catalog product would you like?",
                 "quantity": "How many would you like?",
                 "both": "Which catalog products would you like, and how many of each?"}
    view.note = questions[missing]
    return {"question": view.note}


class Assistant:
    def __init__(self, client, *, project: Path, state_directory: Path, clock):
        self.client, self.project, self.state_directory, self.clock = client, project, state_directory, clock
        self.agent = None

    async def __aenter__(self):
        global _bridge
        if _bridge is not None:
            raise RuntimeError("Only one shop assistant may run in this process")
        os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
        os.environ["RASA_TELEMETRY_ENABLED"] = "false"
        from importlib.metadata import version
        if version("rasa-pro") != "3.21.0.dev5":
            raise RuntimeError("Use the example's locked Rasa environment")
        from rasa.utils.licensing import validate_license_from_env
        validate_license_from_env()
        from rasa.mantle.model_archive.snapshot import package_model_archive
        from rasa.core.config.configuration import Configuration
        from rasa.core.config.available_endpoints import AvailableEndpoints
        from rasa.core.agent import load_agent
        from rasa.mantle.processor import MantleMessageProcessor
        directory = self.state_directory / "models" / uuid4().hex
        directory.mkdir(mode=0o700, parents=True)
        package = package_model_archive(str(self.project / "agent.yml"), str(directory), validate=True)
        if package.code:
            raise RuntimeError("The agent project did not validate")
        Configuration.initialise_empty_endpoints()
        Configuration.initialise_sub_agents(None)
        self.agent = await load_agent(model_path=str(package.model), endpoints=AvailableEndpoints())
        if not isinstance(self.agent.processor, MantleMessageProcessor):
            await self.agent.close()
            self.agent = None
            raise RuntimeError("The native Mantle processor did not load")
        _bridge = self.client
        return self

    async def __aexit__(self, *error):
        global _bridge
        try:
            if self.agent is not None:
                await self.agent.close()
        finally:
            _bridge = None

    async def respond(self, message, latest_order):
        from rasa.core.channels.channel import UserMessage, CollectingOutputChannel
        if self.agent is None:
            raise RuntimeError("The native assistant is not open")
        view = TurnView(latest_order=latest_order)
        token = _view.set(view)
        try:
            async with asyncio.timeout(45):
                await self.agent.handle_message(UserMessage(message.text, output_channel=CollectingOutputChannel(),
                    sender_id="shop-operator", input_channel="telegram", message_id=str(message.update_id)))
            if view.quote is not None:
                return view.quote
            if view.order is not None:
                return f"Order {view.order.number}: {view.order.status}."
            if view.catalog is not None:
                return "\n".join(f"{p.code}: {p.name}, {money(p.price_cents, view.catalog.currency)}; available {p.stock}."
                                 for p in view.catalog.products) or "The catalog is empty."
            return view.note or "Ask for the catalog, a priced basket, or your order's status."
        finally:
            view.active = False
            _view.reset(token)
