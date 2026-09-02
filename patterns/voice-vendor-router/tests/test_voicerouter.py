#!/usr/bin/env python3
"""Unit tests for the router. No network, no credentials, no models.

Everything here is a decision the router makes — how a failure is classified,
whether a voice may change, who is tried next — rather than whether a vendor
happens to be up. Those decisions are the part that has to keep working when
someone else changes the code, and they are exactly what live testing against
real vendors cannot pin down.

    make test
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicerouter.audio import PcmStreamConverter, strip_wav_header  # noqa: E402
from voicerouter.base import ProviderSpec, RouterPolicy  # noqa: E402
from voicerouter.failures import (  # noqa: E402
    FailureKind,
    classify,
    cooldown_for,
    justifies_voice_change,
    should_retry_same_provider,
)
from voicerouter.health import (  # noqa: E402
    HealthRegistry,
    reset_shared_registries,
    shared_registry,
)
from voicerouter.metrics import reset_shared_metrics, shared_metrics  # noqa: E402
from voicerouter.utterance import UtterancePolicy  # noqa: E402


def http_error(status: int, message: str = "", headers=None):
    """A realistic aiohttp error; its __str__ needs a request_info."""
    import aiohttp

    return aiohttp.ClientResponseError(
        mock.Mock(real_url="https://vendor.example/v1"), (),
        status=status, message=message, headers=headers or {},
    )


class TestFailureClassification(unittest.TestCase):
    """The classifier decides how long a provider is skipped, so it has to be right."""

    def test_rejected_key_is_permanent(self):
        for status in (401, 403):
            v = classify(http_error(status, "Unauthorized"))
            self.assertEqual(v.kind, FailureKind.AUTH)
            self.assertTrue(v.permanent, status)

    def test_malformed_request_is_permanent(self):
        # Retrying a request the vendor cannot parse is never going to work.
        v = classify(http_error(400, "Bad Request"))
        self.assertEqual(v.kind, FailureKind.CONFIG)
        self.assertTrue(v.permanent)

    def test_out_of_credits_is_a_long_park_not_a_disable(self):
        v = classify(http_error(402, "Payment Required"))
        self.assertEqual(v.kind, FailureKind.QUOTA)
        self.assertFalse(v.permanent)
        self.assertGreater(cooldown_for(v, 30), 60)

    def test_rate_limit_honours_retry_after(self):
        v = classify(http_error(429, "Too Many Requests", {"Retry-After": "7"}))
        self.assertEqual(v.kind, FailureKind.RATE_LIMIT)
        self.assertEqual(cooldown_for(v, 30), 7.0)

    def test_429_carrying_quota_text_is_quota_not_rate_limit(self):
        # Vendors dress billing up as throttling; the body is the giveaway.
        v = classify(http_error(429, "You exceeded your current quota"))
        self.assertEqual(v.kind, FailureKind.QUOTA)

    def test_aws_throttling_arrives_as_400_and_must_not_disable(self):
        # The regression this branch exists for: a status-only reading would
        # permanently disable a vendor that only asked us to slow down.
        from botocore.exceptions import ClientError

        exc = ClientError(
            {"Error": {"Code": "ThrottlingException"},
             "ResponseMetadata": {"HTTPStatusCode": 400}}, "SynthesizeSpeech")
        v = classify(exc)
        self.assertEqual(v.kind, FailureKind.RATE_LIMIT)
        self.assertFalse(v.permanent)

    def test_status_is_read_from_the_message_when_wrapped(self):
        # Rasa's own wrapper keeps the number but loses the attribute, and the
        # word "Connection" used to win, filing a permanent config error as a
        # transient blip retried every thirty seconds.
        v = classify(RuntimeError("Connection to Rime TTS failed with status 400"))
        self.assertEqual(v.kind, FailureKind.CONFIG)
        self.assertTrue(v.permanent)

    def test_a_number_that_is_not_a_status_is_not_read_as_one(self):
        v = classify(RuntimeError("failed after 500 attempts"))
        self.assertEqual(v.kind, FailureKind.UNKNOWN)

    def test_classify_never_raises_even_on_a_broken_exception(self):
        class Hostile(Exception):
            def __str__(self):
                raise ValueError("nope")

        # A classifier that dies takes the call with it.
        self.assertIsInstance(classify(Hostile()), type(classify(RuntimeError("x"))))


class TestVoiceChangePolicy(unittest.TestCase):
    """Switching provider means the caller hears a different person mid-call."""

    def test_only_genuine_unavailability_justifies_a_new_voice(self):
        for exc, expected in (
            (http_error(402, "Payment Required"), True),   # out of credits
            (TimeoutError("timed out"), True),            # unreachable
            (http_error(401, "Unauthorized"), True),      # rejected key
            (http_error(400, "Bad Request"), True),       # broken config
            (http_error(429, "Too Many"), False),         # slow down
            (http_error(503, "Unavailable"), False),      # momentary wobble
        ):
            v = classify(exc)
            self.assertEqual(justifies_voice_change(v), expected, v.kind)

    def test_retry_same_is_the_inverse(self):
        for exc in (http_error(429, "x"), http_error(503, "x"),
                    http_error(402, "x"), TimeoutError("x")):
            v = classify(exc)
            self.assertEqual(should_retry_same_provider(v), not justifies_voice_change(v))


class TestHealth(unittest.TestCase):
    def setUp(self):
        reset_shared_registries()

    def test_permanent_failure_disables_and_success_does_not_revive_it(self):
        h = HealthRegistry().get("elevenlabs")
        h.record_failure(http_error(401, "Unauthorized"))
        self.assertTrue(h.disabled)
        self.assertFalse(h.is_available())
        # A later success cannot happen for a rejected key; if one somehow
        # does, it must not quietly re-enable a provider an operator has to fix.
        h.record_success()
        self.assertTrue(h.disabled)

    def test_rate_limit_uses_the_vendors_own_window(self):
        h = HealthRegistry().get("openai")
        h.record_failure(http_error(429, "Too Many", {"Retry-After": "7"}))
        self.assertFalse(h.is_available())
        # The vendor's hint wins over any local default.
        self.assertAlmostEqual(h.current_cooldown, 7.0, places=3)

    def test_retry_after_has_a_floor_so_we_never_hammer(self):
        # A vendor asking for 50ms should still not be retried 20x a second.
        h = HealthRegistry().get("openai")
        h.record_failure(http_error(429, "Too Many", {"Retry-After": "0.05"}))
        self.assertGreaterEqual(h.current_cooldown, 1.0)

    def test_a_circuit_actually_reopens(self):
        h = HealthRegistry(cooldown_seconds=0.05).get("deepgram")
        h.record_failure(RuntimeError("something odd"))   # unknown -> default
        h.current_cooldown = 0.05                         # shorten for the test
        self.assertFalse(h.is_available())
        time.sleep(0.07)
        self.assertTrue(h.is_available())
        self.assertEqual(h.state, "half-open")

    def test_configured_cooldown_reaches_the_kinds_it_is_meant_to(self):
        # It was once configurable and inert: every kind had a hard-coded entry,
        # so the number an operator set was read and then never used.
        reg = HealthRegistry(cooldown_seconds=120.0)
        reg.get("gone").record_failure(ConnectionRefusedError("refused"))
        self.assertEqual(reg.get("gone").current_cooldown, 120.0)
        reg.get("odd").record_failure(RuntimeError("something nobody has seen"))
        self.assertEqual(reg.get("odd").current_cooldown, 120.0)

    def test_vendor_semantics_still_win_over_the_configured_default(self):
        # A billing window is not a matter of taste, so the knob must not
        # shorten it.
        reg = HealthRegistry(cooldown_seconds=5.0)
        reg.get("broke").record_failure(http_error(402, "Payment Required"))
        self.assertEqual(reg.get("broke").current_cooldown, 900.0)

    def test_quota_parks_far_longer_than_a_transient_error(self):
        reg = HealthRegistry()
        reg.get("a").record_failure(http_error(402, "Payment Required"))
        reg.get("b").record_failure(http_error(503, "Unavailable"))
        self.assertGreater(reg.get("a").reopens_in, reg.get("b").reopens_in * 5)

    def test_registry_is_shared_per_kind_so_it_outlives_a_call(self):
        # Rasa builds engines per call; call-scoped health would be forgotten
        # at every hangup and rediscovered by the next caller.
        shared_registry("tts").get("rime").record_failure(http_error(401, "no"))
        self.assertTrue(shared_registry("tts").get("rime").disabled)
        self.assertFalse(shared_registry("asr").get("rime").disabled)

    def test_reset_clears_it(self):
        shared_registry("tts").get("rime").record_failure(http_error(401, "no"))
        reset_shared_registries()
        self.assertFalse(shared_registry("tts").get("rime").disabled)


class TestCandidateSelection(unittest.TestCase):
    """Who gets tried, in what order."""

    def _router(self, labels, policy=None):
        from voicerouter.base import BuiltProvider
        from voicerouter.routed_tts import RoutedTTS

        providers = [
            BuiltProvider(ProviderSpec(name=l, label=l, config={}), object())
            for l in labels
        ]
        return RoutedTTS(providers, RouterPolicy.from_dict(policy or {}))

    def setUp(self):
        reset_shared_registries()
        reset_shared_metrics()

    def test_configured_order_by_default(self):
        r = self._router(["a", "b", "c"])
        self.assertEqual(r._candidates(), [0, 1, 2])

    def test_cooling_providers_drop_below_healthy_ones_but_stay(self):
        # A vendor rate-limited ten seconds ago still beats silence.
        r = self._router(["a", "b"])
        r._health.get("a").record_failure(http_error(429, "Too Many"))
        self.assertEqual(r._candidates(), [1, 0])

    def test_disabled_providers_are_dropped_entirely(self):
        # They fail identically every time; trying one only delays the one
        # that might work.
        r = self._router(["a", "b"])
        r._health.get("a").record_failure(http_error(401, "Unauthorized"))
        self.assertEqual(r._candidates(), [1])

    def test_latency_selection_prefers_the_measured_winner(self):
        r = self._router(["slow", "fast"], {"selection": "latency"})
        for _ in range(5):
            r._metrics.record_success("slow", 800.0)
            r._metrics.record_success("fast", 90.0)
        self.assertEqual(r._candidates()[0], 1)

    def test_latency_selection_keeps_configured_order_without_evidence(self):
        # One lucky call must not reorder the chain.
        r = self._router(["a", "b"], {"selection": "latency"})
        r._metrics.record_success("b", 10.0)
        self.assertEqual(r._candidates(), [0, 1])

    def test_utterance_preference_reorders_but_never_restricts(self):
        r = self._router(["premium", "cheap"])
        r._utterance = UtterancePolicy.from_dict(
            {"filler": {"max_chars": 20, "prefer": ["cheap"]}}
        )
        self.assertEqual(r._candidates_for("One moment.")[0], 1)
        # The premium voice is still reachable if the cheap one is down.
        self.assertIn(0, r._candidates_for("One moment."))
        self.assertEqual(r._candidates_for("A much longer disclosure sentence.")[0], 0)


class TestUtteranceClassification(unittest.TestCase):
    def test_length_and_pattern_rules(self):
        p = UtterancePolicy.from_dict(
            {"filler": {"max_chars": 32, "patterns": [r"^(ok|got it|one moment)\b"],
                        "prefer": ["cheap"]}}
        )
        self.assertEqual(p.classify("One moment."), "filler")
        self.assertEqual(p.classify("Got it, checking."), "filler")
        self.assertEqual(p.classify("Transferring four hundred pounds to Sam."), "default")

    def test_a_class_with_no_rule_is_rejected(self):
        # Otherwise a typo silently captures every utterance.
        with self.assertRaises(ValueError):
            UtterancePolicy.from_dict({"oops": {}})

    def test_unknown_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            UtterancePolicy.from_dict({"oops": {"maxchars": 10}})


class TestAudioConversion(unittest.TestCase):
    """Getting this wrong is audible, not raisable."""

    def _tone(self, seconds=1, rate=24000):
        import math
        import struct

        return b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * t / rate)))
            for t in range(rate * seconds)
        )

    def test_duration_is_preserved_across_odd_chunk_boundaries(self):
        from rasa.core.channels.voice_stream.audio_bytes import (
            L16_24KHZ, L16_48KHZ, MULAW_8KHZ,
        )

        pcm = self._tone()
        for fmt in (L16_24KHZ, MULAW_8KHZ, L16_48KHZ):
            conv = PcmStreamConverter(24000, fmt)
            # 1023 bytes splits a 2-byte frame on nearly every boundary.
            out = b"".join(conv.feed(pcm[i:i + 1023]) for i in range(0, len(pcm), 1023))
            self.assertAlmostEqual(len(out) / fmt.bytes_per_second, 1.0, places=2, msg=fmt)

    def test_wav_header_is_located_not_assumed(self):
        import struct

        pcm = self._tone(rate=16000)[:32000]
        header = (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
                  + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
                  + b"data" + struct.pack("<I", len(pcm)))
        body, rate = strip_wav_header(header + pcm)
        self.assertEqual(len(body), len(pcm))
        self.assertEqual(rate, 16000)

    def test_non_wav_passes_through(self):
        self.assertEqual(strip_wav_header(b"rawpcmbytes"), (b"rawpcmbytes", None))


class TestEngineContract(unittest.TestCase):
    """The router is not an engine subclass, so this is what keeps it honest."""

    def test_router_covers_everything_rasa_calls(self):
        from voicerouter import contract

        self.assertEqual(contract.check(verbose=False), [])


class TestVendorCatalogue(unittest.TestCase):
    """CATALOGUE is data nothing imports at runtime — that is its point, and
    also its risk. A typo'd dotted path or a renamed engine class would only
    surface when a user configures that vendor, which is the worst time.
    These tests keep the catalogue true in both directions, offline.
    """

    @staticmethod
    def _bases():
        from rasa.core.channels.voice_stream.asr.asr_engine import ASREngine
        from rasa.core.channels.voice_stream.tts.tts_engine import TTSEngine

        return {"asr": ASREngine, "tts": TTSEngine}

    def test_every_catalogue_path_imports_and_matches_its_kind(self):
        import importlib

        from voicerouter.providers import CATALOGUE

        bases = self._bases()
        for entry in CATALOGUE:
            with self.subTest(path=entry.dotted_path):
                module_name, class_name = entry.dotted_path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                self.assertTrue(
                    issubclass(cls, bases[entry.kind]),
                    f"{entry.dotted_path} is catalogued as {entry.kind!r} but "
                    f"does not subclass {bases[entry.kind].__name__}",
                )

    def test_every_shipped_engine_is_catalogued(self):
        """The other direction: an adapter added to providers/ without a
        catalogue row is invisible to `make probe` and the docs."""
        import importlib
        import inspect
        import pkgutil

        import voicerouter.providers as pkg
        from voicerouter.providers import CATALOGUE

        bases = tuple(self._bases().values())
        catalogued = {e.dotted_path for e in CATALOGUE}
        missing = []
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name.startswith("_"):
                continue  # shared machinery, not vendor surface
            module = importlib.import_module(f"{pkg.__name__}.{info.name}")
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if (
                    cls.__module__ == module.__name__
                    and issubclass(cls, bases)
                    and cls not in bases
                    and not name.startswith("_")
                ):
                    dotted = f"{module.__name__}.{name}"
                    if dotted not in catalogued:
                        missing.append(dotted)
        self.assertEqual(
            missing, [],
            "shipped engine(s) absent from CATALOGUE - add a VendorEntry "
            "so `make probe` and the docs can see them",
        )

    def test_every_catalogued_env_var_is_discoverable(self):
        """An env var the catalogue names but .env.example never mentions is a
        credential a reader has no way to discover."""
        import re

        from voicerouter.providers import CATALOGUE

        example = (Path(__file__).resolve().parent.parent / ".env.example").read_text(
            encoding="utf-8"
        )
        for entry in CATALOGUE:
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", entry.env_var):
                continue  # "(none — local)" and credential-chain notes
            with self.subTest(env=entry.env_var):
                self.assertIn(
                    entry.env_var, example,
                    f"{entry.env_var} (used by {entry.dotted_path}) is missing "
                    f"from .env.example",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
