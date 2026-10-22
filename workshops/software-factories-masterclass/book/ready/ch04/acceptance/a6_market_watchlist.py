"""Acceptance for task A6, the market watchlist card. Written before any candidate existed, from the task text and
SPEC sections 3 to 6 only. The builder never sees this file.

Each check runs the candidate's briefing.market_card.market_card in a child process (a6_child.py) against a mocked ECB
source, so candidate code never runs inside the process that decides, and reads one JSON line back.

K1 the rows are the traveller's currencies, with the source's prices, and no others
K2 the publication day is shown, as a daily reference rate
K3 the card says "daily reference rate, not a live quote" and never calls a rate live or real time
K4 the day-on-day change is computed from the two reference days, named, with the right numbers
K5 when the source fails, the card is unavailable with a reason, and shows no rate: not an invented one, not an old one
K6 a garbage, zero or partial source answer is unavailable, never a zero or a made-up row
L1 exactly one provenance label (PROVIDER DATA) and exactly one freshness line on the card; no REPLAY, no DELAYED
M1 the payload never says live and never says delayed for a daily rate
K7 the card says currencies only, with market hours not provided
K2 also: after a weekend the card shows the last publication day, never today
K4 also: with one reference day the change is unavailable, never zero
N1 the candidate has no network of its own (enforced by an OS sandbox)
"""
import html as _html
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
    done = subprocess.run(command(str(HERE / "a6_child.py"), PRODUCT, scenario, NONCE), capture_output=True, text=True,
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


class MarketWatchlist(unittest.TestCase):
    def test_k1_rows_are_the_travellers_currencies_with_the_sources_prices(self):
        symbols = {q["symbol"]: q["price"] for q in built("ok")["payload"]["symbols"]}
        self.assertEqual(symbols, {"EURGBP": 0.87, "EURUSD": 1.165})

    def test_k1_a_currency_not_asked_for_adds_no_row(self):
        symbols = [q["symbol"] for q in built("usd_only")["payload"]["symbols"]]
        self.assertEqual(symbols, ["EURUSD"])

    def test_k2_the_publication_day_is_shown_as_a_daily_reference_rate(self):
        result = built("ok")
        self.assertEqual(result["payload"]["rate_basis"], "daily_reference")
        self.assertEqual(result["payload"]["quote_date"], "2026-10-21")
        self.assertIn("2026-10-21", result["text"])

    def test_k3_the_card_says_not_a_live_quote_and_never_says_live_or_real_time(self):
        text = built("ok")["text"]
        self.assertIn(FRESH, text)
        rest = without_phrase(text).lower()
        for word in ("live", "real time", "real-time", "realtime", "streaming"):
            self.assertNotIn(word, rest)

    def test_k4_the_change_is_computed_from_two_named_reference_days(self):
        result = built("ok")
        quotes = {q["symbol"]: q for q in result["payload"]["symbols"]}
        self.assertAlmostEqual(quotes["EURUSD"]["change"], 0.0019, places=6)
        self.assertAlmostEqual(quotes["EURUSD"]["change_pct"], 0.0019 / 1.1631 * 100, places=5)
        self.assertAlmostEqual(quotes["EURGBP"]["change"], -0.0023, places=6)
        self.assertIn("change_computed_from_two_reference_days", result["assumptions"])
        self.assertIn("COMPUTED", result["text"])
        self.assertIn("2026-10-20", result["text"])
        self.assertIn("2026-10-21", result["text"])

    def test_k5_a_failed_source_is_unavailable_and_shows_no_rate(self):
        result = built("failure")
        self.assertTrue(result["error"], "an unavailable card needs a reason")
        self.assertIsNone(result["payload"])
        self.assertIn("unavailable", result["text"].lower())
        for number in ("1.165", "0.87", "1.08", "0.85"):
            self.assertNotIn(number, result["text"])

    def test_k5_after_a_good_read_a_later_failure_does_not_bring_back_the_old_rate(self):
        result = built("after_failure")
        self.assertTrue(result["error"])
        self.assertIsNone(result["payload"])
        for number in ("1.165", "0.87"):
            self.assertNotIn(number, result["text"])

    def test_k6_garbage_zero_or_partial_answers_are_unavailable_never_a_zero_row(self):
        for scenario in ("garbage", "zero", "missing_gbp"):
            result = built(scenario)
            self.assertTrue(result["error"], scenario)
            self.assertIsNone(result["payload"], scenario)

    def test_l1_one_provenance_label_and_one_freshness_line(self):
        text = built("ok")["text"]
        self.assertEqual(text.count("PROVIDER DATA"), 1)
        self.assertEqual(text.count(FRESH), 1)
        for forbidden in ("REPLAY", "DELAYED"):
            self.assertNotIn(forbidden, text)

    def test_m1_the_payload_never_says_live_or_delayed_for_a_daily_rate(self):
        payload = built("ok")["payload"]
        self.assertNotEqual(payload["rate_basis"], "live")
        self.assertIs(payload["delayed"], False)
        self.assertIsNone(payload["quote_time"])

    def test_n1_the_candidate_has_no_network_of_its_own(self):
        """Enforced by the OS sandbox the candidate runs in: a connection from inside it must fail."""
        self.assertIsNotNone(SANDBOX, "N1 cannot be enforced on this machine: no sandbox-exec; run the factory where it exists")
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        probe = "import socket,sys\ntry:\n socket.create_connection(('127.0.0.1',%d),timeout=2)\nexcept OSError:\n sys.exit(0)\nsys.exit(1)\n" % port
        done = subprocess.run([SANDBOX, "-p", PROFILE, sys.executable, "-I", "-c", probe], timeout=20,
                              env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})
        listener.close()
        self.assertEqual(done.returncode, 0, "the sandbox did not stop a connection")

    def test_k2_a_weekend_card_shows_the_last_publication_day_never_today(self):
        result = built("weekend")
        self.assertEqual(result["payload"]["quote_date"], "2026-10-16")
        self.assertIn("2026-10-16", result["text"])
        self.assertRegex(result["text"], r"published: ?2026-10-16")
        self.assertNotRegex(result["text"], r"published: ?2026-10-19")  # the fetch time may say today; the rate's day may not

    def test_k4_one_reference_day_says_change_unavailable_never_zero(self):
        result = built("single_day")
        self.assertIsNone(result["error"])
        for quote in result["payload"]["symbols"]:
            self.assertIsNone(quote["change"])
            self.assertIsNone(quote["change_pct"])
        self.assertNotIn("change_computed_from_two_reference_days", result["assumptions"])
        self.assertRegex(result["text"].lower(), r"change[^.]{0,40}(unavailable|not provided|not available)")
        self.assertNotRegex(result["text"], r"(?<![0-9.])0(\.0+)? ?%")

    def test_k7_the_card_says_currencies_only(self):
        self.assertIn("Currencies only", built("ok")["text"])


if __name__ == "__main__":
    unittest.main()
