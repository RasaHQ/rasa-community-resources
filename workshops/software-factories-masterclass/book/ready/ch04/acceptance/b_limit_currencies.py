"""Acceptance for task B: the market card shows at most a limit of currencies. Written before any attempt existed.
The limit is the number in the task file. The builder never sees this file.
Each check runs the attempt's briefing.market_card.market_card in a child process (b_child.py) with no network and reads one JSON line back.

B1 asking for four currencies shows at most the limit
B2 the rows shown are the first ones in alphabetical order
B3 asking for fewer currencies than the limit shows all of them
B4 the card keeps its labels: one PROVIDER DATA label and one freshness line
B5 when the source fails the card is unavailable and shows no rate
B6 the attempt has no network of its own (enforced by an OS sandbox)
"""
import html as _html
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import unittest
from pathlib import Path

from zeo_core.adapters import widget_html
from zeo_core.contracts.ui import widgets as W

HERE = Path(__file__).resolve().parent
PRODUCT = os.environ.get("PRODUCT_PROJECT") or os.environ["MANTLE_PROJECT"]
TASK = json.loads((HERE.parent / "tasks" / "b-limit-currencies.json").read_text())
LIMIT = TASK["limit"]
if not isinstance(LIMIT, int) or isinstance(LIMIT, bool) or not 1 <= LIMIT <= 3:
    raise SystemExit("Set a limit from 1 to 3 in tasks/b-limit-currencies.json first")
NONCE = "A6RESULT:" + secrets.token_hex(8) + ":"


SANDBOX = shutil.which("sandbox-exec")
PROFILE = "(version 1)(allow default)(deny network*)"


def plain(text):
    text = re.sub(r"<style>.*?</style>", "", text, flags=re.S)
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))).strip()


def command(*args):
    base = [sys.executable, "-I", *args]
    return [SANDBOX, "-p", PROFILE, *base] if SANDBOX else base


def run(scenario):
    """Run the candidate in a child with no network, take exactly one result line, validate and render it here."""
    done = subprocess.run(command(str(HERE / "b_child.py"), PRODUCT, scenario, NONCE), capture_output=True, text=True,
                          timeout=60, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "PYTHONDONTWRITEBYTECODE": "1"})
    lines = [line for line in done.stdout.splitlines() if NONCE in line]
    if len(lines) != 1 or not lines[0].startswith(NONCE):
        raise AssertionError("the candidate must produce exactly one result: found %d" % len(lines)
                             + " (" + (done.stderr.strip().splitlines() or ["no error output"])[-1][:160] + ")")
    try:
        ref = W.DataRef.model_validate_json(lines[0][len(NONCE):])
        ref.check("market_watchlist")
    except Exception as exc:  # noqa: BLE001
        raise AssertionError("the card is not a valid market_watchlist DataRef: " + type(exc).__name__)
    card = W.CardState(widget_id="market-watchlist", component="market_watchlist", revision=1, request_id="r1",
                       replaced=False, data_ref=ref)
    return {"error": ref.error.reason if ref.error else None, "payload": None if ref.error else ref.payload,
            "assumptions": [a.label for a in ref.assumptions], "text": plain(widget_html.render_card_html(card))}


def built(scenario):
    return run(scenario)


FRESH = "daily reference rate, not a live quote"


def without_phrase(text):
    return text.replace(FRESH, "")


class LimitedMarketCard(unittest.TestCase):
    def test_b1_four_currencies_show_at_most_the_limit(self):
        symbols = [q["symbol"] for q in built("many")["payload"]["symbols"]]
        self.assertLessEqual(len(symbols), LIMIT)
        self.assertGreaterEqual(len(symbols), 1)

    def test_b2_the_rows_shown_are_the_first_ones_in_alphabetical_order(self):
        symbols = [q["symbol"] for q in built("many")["payload"]["symbols"]]
        self.assertEqual(symbols, ["EURCHF", "EURGBP", "EURJPY", "EURUSD"][:LIMIT])

    def test_b3_fewer_currencies_than_the_limit_shows_all_of_them(self):
        symbols = [q["symbol"] for q in built("few")["payload"]["symbols"]]
        self.assertEqual(symbols, ["EURUSD"])

    def test_b4_the_card_keeps_its_labels(self):
        text = built("many")["text"]
        self.assertEqual(text.count("PROVIDER DATA"), 1)
        self.assertEqual(text.count(FRESH), 1)
        self.assertNotIn("REPLAY", text)

    def test_b5_a_failed_source_is_unavailable_and_shows_no_rate(self):
        result = built("failure")
        self.assertTrue(result["error"])
        self.assertIsNone(result["payload"])
        self.assertIn("unavailable", result["text"].lower())

    def test_b6_the_attempt_has_no_network_of_its_own(self):
        """Enforced by the OS sandbox the attempt runs in: a connection from inside it must fail."""
        self.assertIsNotNone(SANDBOX, "this check cannot be enforced on this machine: no sandbox-exec")
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        probe = "import socket,sys\ntry:\n socket.create_connection(('127.0.0.1',%d),timeout=2)\nexcept OSError:\n sys.exit(0)\nsys.exit(1)\n" % port
        done = subprocess.run([SANDBOX, "-p", PROFILE, sys.executable, "-I", "-c", probe], timeout=20, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})
        listener.close()
        self.assertEqual(done.returncode, 0, "the sandbox did not stop a connection")


if __name__ == "__main__":
    unittest.main()
