"""One operator conversation, with confirmation and send receipts owned by the host."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import Field

from .models import Order, Quote, Record, money, review
from .state import open_state


class Incoming(Record):
    update_id: int = Field(ge=0)
    message_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    date: int = Field(ge=0)
    text: str | None = Field(max_length=4096)
    edited: bool = False

    @classmethod
    def operator_message(cls, raw, chat_id):
        message = raw.get("message") or raw.get("edited_message")
        if not isinstance(message, dict):
            return None
        chat, sender = message.get("chat", {}), message.get("from", {})
        if (chat.get("id") != chat_id or chat.get("type") != "private"
                or sender.get("id") != chat_id or sender.get("is_bot") is not False):
            return None
        return cls(update_id=raw["update_id"], message_id=message["message_id"], chat_id=chat_id,
                   date=message["date"], text=message.get("text"), edited="edited_message" in raw)


class Sent(Record):
    message_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    date: int = Field(ge=0)
    text: str


class Held(RuntimeError):
    pass


class Conversation:
    def __init__(self, path: Path, *, chat_id: int, telegram, assistant, orders, clock):
        self.chat_id, self.telegram, self.assistant, self.orders, self.clock = chat_id, telegram, assistant, orders, clock
        self.db = open_state(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS inbox (update_id INTEGER PRIMARY KEY, original TEXT NOT NULL, phase TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outgoing (key TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, text TEXT NOT NULL, receipt TEXT);
            CREATE TABLE IF NOT EXISTS review (singleton INTEGER PRIMARY KEY CHECK(singleton=1), quote TEXT NOT NULL, receipt TEXT NOT NULL, watermark INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS contacts (order_number TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, notified INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS quarantine (update_id INTEGER PRIMARY KEY, reason TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def retain(self, payloads):
        """Save the entire returned batch before advancing a provider offset."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            previous_id = -1
            for raw in payloads:
                number = raw.get("update_id")
                if type(number) is not int or number < 0 or number <= previous_id:
                    raise Held("UPDATE_ORDER_INVALID")
                previous_id = number
                original = json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)
                old = self.db.execute("SELECT original FROM inbox WHERE update_id=?", (number,)).fetchone()
                if old and old[0] != original:
                    raise Held("ORIGINAL_UPDATE_CHANGED")
                self.db.execute("INSERT OR IGNORE INTO inbox VALUES(?,?,'saved')", (number, original))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def offset(self):
        value = self.db.execute("SELECT MAX(update_id) FROM inbox").fetchone()[0]
        return None if value is None else value + 1

    def saved(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT original FROM inbox WHERE phase='saved' ORDER BY update_id")]

    def quarantine(self, raw):
        number = raw["update_id"]
        self.db.execute("INSERT OR IGNORE INTO quarantine VALUES(?,?)", (number, "UNSUPPORTED_PROVIDER_UPDATE"))
        changed = self.db.execute("UPDATE inbox SET phase='quarantined' WHERE update_id=? AND phase='saved'", (number,))
        if changed.rowcount:
            print("A Telegram update needs private inspection. Check the local journal.", flush=True)
        message = raw.get("message") or raw.get("edited_message")
        chat = message.get("chat") if isinstance(message, dict) else None
        if isinstance(chat, dict) and chat.get("id") == self.chat_id:
            self.db.execute("DELETE FROM review WHERE singleton=1")

    def assert_restart_safe(self):
        if self.db.execute("SELECT 1 FROM inbox WHERE phase IN ('working','held')").fetchone():
            raise Held("INSPECT_THE_ORIGINAL_TURN_BEFORE_RESTART")
        if self.db.execute("SELECT 1 FROM outgoing WHERE receipt IS NULL").fetchone():
            raise Held("INSPECT_THE_ORIGINAL_SEND_BEFORE_RESTART")

    async def send(self, key, text):
        if not 0 < len(text) <= 4096:
            raise Held("REPLY_TOO_LONG")
        old = self.db.execute("SELECT chat_id,text,receipt FROM outgoing WHERE key=?", (key,)).fetchone()
        if old:
            if old[:2] != (self.chat_id, text) or old[2] is None:
                raise Held("ORIGINAL_SEND_HELD_OR_CHANGED")
            return Sent.model_validate_json(old[2])
        self.db.execute("INSERT INTO outgoing VALUES(?,?,?,NULL)", (key, self.chat_id, text))
        try:
            message = await self.telegram.send_message(self.chat_id, text)
            sent = Sent(message_id=message.message_id, chat_id=message.chat.id, date=message.date, text=message.text)
            if sent.chat_id != self.chat_id or sent.text != text:
                raise Held("SENT_MESSAGE_DOES_NOT_MATCH")
            self.db.execute("UPDATE outgoing SET receipt=? WHERE key=?", (sent.model_dump_json(), key))
            return sent
        except asyncio.CancelledError:
            raise
        except BaseException:
            raise Held("ORIGINAL_SEND_NEEDS_INSPECTION") from None

    async def handle(self, raw):
        number = raw["update_id"]
        stored = self.db.execute("SELECT phase FROM inbox WHERE update_id=?", (number,)).fetchone()
        if stored != ("saved",):
            raise Held("TURN_ALREADY_STARTED_OR_NOT_RETAINED")
        self.db.execute("UPDATE inbox SET phase='working' WHERE update_id=?", (number,))
        try:
            message = Incoming.operator_message(raw, self.chat_id)
            if message is None:
                self.db.execute("UPDATE inbox SET phase='skipped' WHERE update_id=?", (number,))
                return
            pending = self.db.execute("SELECT quote,receipt,watermark FROM review WHERE singleton=1").fetchone()
            self.db.execute("DELETE FROM review WHERE singleton=1")
            key = "reply:" + str(number)
            affirmative = message.text is not None and message.text.strip().casefold() == "confirm"
            if pending and affirmative and not message.edited:
                quote, receipt = Quote.model_validate_json(pending[0]), Sent.model_validate_json(pending[1])
                if (number <= pending[2] or message.message_id <= receipt.message_id or message.date < receipt.date
                        or self.clock() >= quote.expires_at):
                    await self.send(key, "That review is no longer active. Please ask for a new basket.")
                else:
                    order = await self.orders.place(quote.reference, "telegram:" + str(number))
                    if (not isinstance(order, Order) or order.quote != quote
                            or order.request_key != "telegram:" + str(number)):
                        raise Held("ORIGINAL_ORDER_RESPONSE_CHANGED")
                    self.db.execute("INSERT INTO contacts(order_number,chat_id) VALUES(?,?)", (str(order.number), self.chat_id))
                    await self.send(key, f"Order {order.number} is placed. Total: {money(order.quote.total_cents, order.quote.currency)}.")
            elif affirmative:
                await self.send(key, "There is no active review. Please ask for a basket first.")
            elif not message.text or message.edited:
                await self.send(key, "Please send a new text message. Any earlier review has been canceled.")
            elif message.text.strip().casefold() in {"cancel", "no", "stop"}:
                await self.send(key, "The review is canceled. No order was placed from it.")
            else:
                result = await self.assistant.respond(message, self.latest_order())
                if isinstance(result, Quote):
                    if self.clock() >= result.expires_at:
                        raise Held("PRICE_REVIEW_EXPIRED")
                    receipt = await self.send(key, review(result))
                    watermark = self.db.execute("SELECT MAX(update_id) FROM inbox").fetchone()[0]
                    self.db.execute("INSERT INTO review VALUES(1,?,?,?)", (result.model_dump_json(), receipt.model_dump_json(), watermark))
                else:
                    await self.send(key, result)
            self.db.execute("UPDATE inbox SET phase='done' WHERE update_id=?", (number,))
        except BaseException:
            self.db.execute("UPDATE inbox SET phase='held' WHERE update_id=?", (number,))
            raise

    def latest_order(self):
        row = self.db.execute("SELECT order_number FROM contacts ORDER BY rowid DESC LIMIT 1").fetchone()
        return row[0] if row else None

    async def notify_shipments(self):
        for number, chat_id in self.db.execute("SELECT order_number,chat_id FROM contacts WHERE notified=0").fetchall():
            if chat_id != self.chat_id:
                raise Held("ORDER_RECIPIENT_CHANGED")
            order = await self.orders.lookup(number)
            if str(order.number) != number:
                raise Held("ORDER_RESPONSE_CHANGED")
            if order.status == "shipped":
                await self.send("shipment:" + number, f"Your order {number} has shipped.")
                self.db.execute("UPDATE contacts SET notified=1 WHERE order_number=?", (number,))
