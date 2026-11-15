"""Confirmation and delivery boundaries with real state and fake providers."""
from datetime import datetime, timedelta, timezone
import asyncio
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from shop_demo.conversation import Conversation, Held
from shop_demo.models import Basket, BasketItem
from shop_demo.shop import Shop
from test_shop import MemoryTables


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 11, 16, 10, tzinfo=timezone.utc)
        self.tables = MemoryTables()
        self.shop = Shop(self.tables, journal=self.root / "shop.sqlite3", currency="MXN", clock=lambda: self.now)
        owner = self

        class Telegram:
            def __init__(self):
                self.next_id, self.sent, self.fail = 101, [], False

            async def send_message(self, chat_id, text):
                self.sent.append((chat_id, text))
                if self.fail:
                    raise TimeoutError("synthetic")
                message = SimpleNamespace(message_id=self.next_id, chat=SimpleNamespace(id=chat_id),
                    date=int(owner.now.timestamp()), text=text)
                self.next_id += 2
                return message

        class Assistant:
            async def respond(self, message, latest_order):
                return owner.shop.quote(Basket(items=(BasketItem(code="NOTEBOOK", quantity=2),)))

        class Orders:
            async def place(self, quote, key):
                from shop_demo.models import PlaceOrder
                return owner.shop.place(PlaceOrder(quote_reference=quote, request_key=key))

            async def lookup(self, number):
                from uuid import UUID
                return owner.shop.lookup(UUID(number))
        self.telegram, self.assistant, self.orders = Telegram(), Assistant(), Orders()
        self.chat = Conversation(self.root / "chat.sqlite3", chat_id=42, telegram=self.telegram,
            assistant=self.assistant, orders=self.orders, clock=lambda: self.now)

    async def asyncTearDown(self):
        self.chat.close()
        self.shop.close()
        self.tmp.cleanup()

    def raw(self, update_id, message_id, text="two notebooks", **changes):
        message = {"message_id": message_id, "date": int(self.now.timestamp()),
            "chat": {"id": 42, "type": "private"}, "from": {"id": 42, "is_bot": False}}
        if text is not None:
            message["text"] = text
        message.update(changes)
        return {"update_id": update_id, "message": message}

    async def receive(self, raw):
        self.chat.retain([raw])
        await self.chat.handle(raw)

    async def review(self):
        await self.receive(self.raw(10, 100))
        self.assertIn("MXN 258.00", self.telegram.sent[-1][1])
        self.assertEqual(self.tables.append_calls, 0)

    async def test_separate_confirmation_places_once_and_shipping_notifies_once(self):
        await self.review()
        self.now += timedelta(seconds=1)
        confirmation = self.raw(11, 102, "confirm")
        await self.receive(confirmation)
        self.assertEqual(self.tables.append_calls, 1)
        self.assertIn("is placed", self.telegram.sent[-1][1])
        with self.assertRaises(Held):
            await self.chat.handle(confirmation)
        self.assertEqual(self.tables.append_calls, 1)
        self.tables.rows["Orders"][1][4] = "shipped"
        await self.chat.notify_shipments()
        sent_count = len(self.telegram.sent)
        self.assertIn("has shipped", self.telegram.sent[-1][1])
        await self.chat.notify_shipments()
        self.assertEqual(len(self.telegram.sent), sent_count)

    async def test_confirm_already_waiting_in_same_batch_cannot_approve_later_prompt(self):
        first, early_yes = self.raw(10, 100), self.raw(11, 101, "confirm")
        self.chat.retain([first, early_yes])
        await self.chat.handle(first)
        await self.chat.handle(early_yes)
        self.assertEqual(self.tables.append_calls, 0)
        self.assertIn("no longer active", self.telegram.sent[-1][1])

    async def test_nontext_first_reply_cancels_review_and_later_confirm_cannot_restore_it(self):
        await self.review()
        self.now += timedelta(seconds=1)
        await self.receive(self.raw(11, 102, None, photo=[{"file_id": "synthetic"}]))
        await self.receive(self.raw(12, 104, "confirm"))
        self.assertEqual(self.tables.append_calls, 0)
        self.assertIn("no active review", self.telegram.sent[-1][1])

    async def test_only_exact_confirm_is_a_confirmation(self):
        await self.review()
        # This is a new request, not a confirmation. A model may quote a new
        # basket, but it cannot place either basket without a separate turn.
        await self.receive(self.raw(11, 102, "confirm and change it"))
        self.assertEqual(self.tables.append_calls, 0)

    async def test_expired_review_is_not_placed(self):
        await self.review()
        self.now += timedelta(minutes=6)
        await self.receive(self.raw(11, 102, "confirm"))
        self.assertEqual(self.tables.append_calls, 0)

    async def test_explicit_cancellation_does_not_ask_model_for_another_review(self):
        await self.review()
        await self.receive(self.raw(11, 102, "cancel"))
        await self.receive(self.raw(12, 104, "confirm"))
        self.assertEqual(self.tables.append_calls, 0)
        self.assertIn("no active review", self.telegram.sent[-1][1])

    async def test_send_cancellation_propagates_and_unknown_send_remains_held(self):
        async def canceled_send(*args):
            raise asyncio.CancelledError("synthetic cancellation")
        self.telegram.send_message = canceled_send
        with self.assertRaises(asyncio.CancelledError):
            await self.receive(self.raw(10, 100))
        with self.assertRaises(Held):
            self.chat.assert_restart_safe()

    async def test_unsupported_update_is_retained_in_quarantine_and_cancels_review(self):
        await self.review()
        raw = self.raw(11, 102, None)
        self.chat.retain([raw])
        self.chat.quarantine(raw)
        self.assertEqual(self.chat.saved(), [])
        self.assertEqual(self.chat.db.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0], 1)
        await self.receive(self.raw(12, 104, "confirm"))
        self.assertEqual(self.tables.append_calls, 0)

    async def test_unknown_send_stays_held_across_restart(self):
        self.telegram.fail = True
        with self.assertRaises(Held):
            await self.receive(self.raw(10, 100))
        calls = len(self.telegram.sent)
        self.chat.close()
        self.chat = Conversation(self.root / "chat.sqlite3", chat_id=42, telegram=self.telegram,
            assistant=self.assistant, orders=self.orders, clock=lambda: self.now)
        with self.assertRaises(Held):
            self.chat.assert_restart_safe()
        self.assertEqual(len(self.telegram.sent), calls)

    async def test_changed_original_or_other_chat_never_reaches_assistant(self):
        raw = self.raw(10, 100)
        self.chat.retain([raw])
        with self.assertRaises(Held):
            self.chat.retain([self.raw(10, 100, "changed")])
        self.assertEqual(self.chat.offset(), 11)
        other = self.raw(11, 100, chat={"id": 99, "type": "private"})
        await self.receive(other)
        self.assertEqual(self.telegram.sent, [])
        self.assertEqual(self.tables.append_calls, 0)
