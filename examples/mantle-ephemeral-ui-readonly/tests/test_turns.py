"""Consumer tests with an explicit validation double, not Core qualification."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest
import threading
from unittest.mock import patch

from lib.mantle_adapter import RetainedRead, show_current
from lib.turns import MAX_BYTES, Refused, TurnView, UNAVAILABLE

NOW = datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)
OPERATION = "zeoconnect.connections.list"  # Synthetic; producer binding pending.


def fixture():
    return {
        "schema": "zeo.ui-result/v1", "result_id": "fixture-result",
        "in_reply_to": {"operation": OPERATION, "invocation": "fixture-invocation"},
        "produced_at": "2026-10-19T10:00:00Z", "complete": False,
        "plain_text": "Synthetic visible connection metadata, not a live read.",
        "components": [{
            "id": "connection-status", "kind": "card",
            "title": "Synthetic connection status",
            "accessibility_label": "Synthetic connection status",
            "fallback_text": "Synthetic connection metadata.",
            "snapshot": {
                "source": {"kind": "operation", "ref": "fixture-invocation"},
                "observed_at": "2026-10-19T10:00:00Z",
            },
            "props": {
                "summary": "Synthetic fixture only",
                "facts": [{"label": "Provider", "value_type": "text", "value": "fixture"}],
                "evidence": [], "action_refs": [],
            },
        }],
    }


class FixtureValidationDouble:
    """Returns a host-owned test object; makes NO schema-validity claim."""

    def __init__(self, value=None):
        self.value = fixture() if value is None else value
        self.calls = 0

    def __call__(self, _raw):
        self.calls += 1
        return deepcopy(self.value)


class ConsumerTests(unittest.TestCase):
    def accept(self, view, turn=None, raw=b"synthetic carrier", **kwargs):
        turn = turn or view.begin(OPERATION, "fixture-invocation")
        return view.accept(
            turn, raw, now=NOW, retained_original=kwargs.get("lookup", lambda *_: True)
        )

    def test_valid_fixture_is_partial_and_inert(self):
        view = TurnView(FixtureValidationDouble())
        self.assertTrue(self.accept(view))
        self.assertIn("Partial view", view.html)
        self.assertIn("Synthetic fixture", view.html)
        self.assertNotIn("<a ", view.html)

    def test_new_turn_clears_old_card_even_without_a_new_tool(self):
        view = TurnView(FixtureValidationDouble())
        self.assertTrue(self.accept(view))
        view.begin(OPERATION, "next-turn")
        self.assertEqual(view.html, "")

    def test_older_completion_and_failure_cannot_change_new_turn(self):
        view = TurnView(FixtureValidationDouble())
        old = view.begin(OPERATION, "old")
        current = view.begin(OPERATION, "fixture-invocation")
        self.assertTrue(self.accept(view, current))
        html = view.html
        self.assertFalse(self.accept(view, old))
        view.fail(old)
        self.assertEqual(view.html, html)

    def test_turn_changes_during_validation_cannot_publish_stale_html(self):
        def validate(_raw):
            view.begin(OPERATION, "newer")
            return fixture()
        view = TurnView(validate)
        old = view.begin(OPERATION, "fixture-invocation")
        self.assertFalse(self.accept(view, old))
        self.assertEqual(view.html, "")

    def test_sessions_do_not_accept_each_others_leases(self):
        a, b = (TurnView(FixtureValidationDouble()) for _ in range(2))
        a_turn = a.begin(OPERATION, "fixture-invocation")
        b.begin(OPERATION, "fixture-invocation")
        self.assertFalse(self.accept(b, a_turn))
        self.assertEqual(b.html, "")

    def test_missing_original_is_not_healthy_empty(self):
        view = TurnView(FixtureValidationDouble())
        self.assertFalse(self.accept(view, lookup=lambda *_: False))
        self.assertEqual(view.html, UNAVAILABLE)

    def test_consumer_policy_refusals(self):
        cases = []
        for field, value in [("schema", "other/v1"), ("complete", True),
                             ("produced_at", "2026-10-19T09:58:00Z"),
                             ("produced_at", "2026-10-19T10:01:00Z")]:
            changed = fixture()
            changed[field] = value
            cases.append(changed)
        changed = fixture()
        changed["in_reply_to"]["invocation"] = "other"
        cases.append(changed)
        changed = fixture()
        changed["in_reply_to"]["operation"] = "other"
        cases.append(changed)
        changed = fixture()
        changed["components"][0]["kind"] = "table"
        cases.append(changed)
        changed = fixture()
        changed["components"].append(deepcopy(changed["components"][0]))
        cases.append(changed)
        changed = fixture()
        changed["components"][0]["props"]["action_refs"] = ["do-something"]
        cases.append(changed)
        for changed in cases:
            with self.subTest(value=changed):
                view = TurnView(FixtureValidationDouble(changed))
                self.assertFalse(self.accept(view))
                self.assertEqual(view.html, UNAVAILABLE)

    def test_old_missing_expired_or_misbound_source_snapshot_is_unavailable(self):
        for change in ["old", "missing", "expired", "wrong", "kind"]:
            value = fixture()
            card = value["components"][0]
            if change == "old":
                card["snapshot"]["observed_at"] = "2026-10-19T09:00:00Z"
            elif change == "missing":
                del card["snapshot"]
            elif change == "expired":
                card["snapshot"]["expires_at"] = "2026-10-19T10:00:00Z"
            elif change == "kind":
                card["snapshot"]["source"]["kind"] = "other"
            else:
                card["snapshot"]["source"]["ref"] = "other-invocation"
            view = TurnView(FixtureValidationDouble(value))
            self.assertFalse(self.accept(view))
            self.assertEqual(view.html, UNAVAILABLE)

    def test_overbound_carrier_does_not_reach_validator(self):
        validator = FixtureValidationDouble()
        view = TurnView(validator)
        self.assertFalse(self.accept(view, raw=b"x" * (MAX_BYTES + 1)))
        self.assertEqual(validator.calls, 0)

    def test_all_canonical_refusals_fail_closed_without_echoing_payload(self):
        # Byte/schema behaviour belongs to Core. Here we verify every refusal
        # replaces the current display, without inventing a local parser.
        for raw in [b'\xff', b'{"x":1,"x":2}', b'{} trailing', b'{"unknown":1}']:
            def refuse(_raw):
                raise Refused("synthetic_core_refusal")
            view = TurnView(refuse)
            turn = view.begin(OPERATION, "fixture-invocation")
            view.html = "old card"
            self.assertFalse(self.accept(view, turn, raw))
            self.assertEqual(view.html, UNAVAILABLE)

    def test_hostile_text_and_evidence_cannot_create_html_or_links(self):
        value = fixture()
        value["components"][0]["title"] = '<img src=x onerror="alert(1)">'
        value["components"][0]["props"]["summary"] = "invisible\u202eend"
        value["components"][0]["props"]["evidence"] = ["https://example.invalid/private"]
        view = TurnView(FixtureValidationDouble(value))
        self.assertTrue(self.accept(view))
        self.assertNotIn("<img", view.html)
        self.assertIn("&lt;img", view.html)
        self.assertIn("\\u202e", view.html)
        self.assertNotIn("<a ", view.html)

    def test_attribute_quotes_and_ascii_controls_are_visible_inert_text(self):
        value = fixture()
        value["components"][0]["accessibility_label"] = '\" onmouseover=\"bad\x00\x1b\x7f'
        view = TurnView(FixtureValidationDouble(value))
        self.assertTrue(self.accept(view))
        self.assertIn('&quot; onmouseover=&quot;bad\\x00\\x1b\\x7f', view.html)
        for char in ('\x00', '\x1b', '\x7f'):
            self.assertNotIn(char, view.html)

    def test_validation_does_not_block_loop_or_publish_after_total_timeout(self):
        release = threading.Event()
        started = threading.Event()
        value = fixture()
        value["produced_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value["components"][0]["snapshot"]["observed_at"] = value["produced_at"]
        def validate(_raw):
            started.set()
            release.wait(timeout=1)
            return value
        view = TurnView(validate)
        async def read():
            return RetainedRead(OPERATION, "fixture-invocation", b"fixture")
        async def check():
            try:
                with patch("lib.mantle_adapter.TURN_BUDGET_SECONDS", 0.05):
                    task = asyncio.create_task(show_current(
                        view, OPERATION, "fixture-invocation", read, lambda *_: True
                    ))
                    await asyncio.sleep(0.02)
                    self.assertTrue(started.is_set())
                    self.assertFalse(release.is_set())  # Event loop still ran.
                    self.assertEqual(await task, {"status": "unavailable"})
                    self.assertEqual(view.html, UNAVAILABLE)
            finally:
                release.set()
            await asyncio.sleep(0.02)
            self.assertEqual(view.html, UNAVAILABLE)  # Late worker has no lease.
        asyncio.run(check())

    def test_failed_read_clears_card_and_does_not_retry(self):
        view = TurnView(FixtureValidationDouble())
        calls = []
        async def denied():
            calls.append("read")
            raise PermissionError("private diagnostic must not escape")
        status = asyncio.run(show_current(
            view, OPERATION, "fixture-invocation", denied, lambda *_: True
        ))
        self.assertEqual(calls, ["read"])
        self.assertEqual(status, {"status": "unavailable"})
        self.assertEqual(view.html, UNAVAILABLE)

    def test_adapter_rejects_mismatched_retained_result(self):
        view = TurnView(FixtureValidationDouble())
        async def wrong():
            return RetainedRead(OPERATION, "wrong", json.dumps(fixture()).encode())
        status = asyncio.run(show_current(
            view, OPERATION, "fixture-invocation", wrong, lambda *_: True
        ))
        self.assertEqual(status, {"status": "unavailable"})
        self.assertEqual(view.html, UNAVAILABLE)

    def test_successful_adapter_reads_once_and_keeps_original_binding(self):
        value = fixture()
        value["produced_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        value["components"][0]["snapshot"]["observed_at"] = value["produced_at"]
        view = TurnView(FixtureValidationDouble(value))
        calls = []
        lookups = []
        async def read():
            calls.append("read")
            return RetainedRead(OPERATION, "fixture-invocation", b"fixture")
        def lookup(operation, invocation):
            lookups.append((operation, invocation))
            return True
        status = asyncio.run(show_current(
            view, OPERATION, "fixture-invocation", read, lookup
        ))
        self.assertEqual(status, {"status": "displayed"})
        self.assertEqual(calls, ["read"])
        self.assertEqual(lookups, [(OPERATION, "fixture-invocation")])


if __name__ == "__main__":
    unittest.main()
