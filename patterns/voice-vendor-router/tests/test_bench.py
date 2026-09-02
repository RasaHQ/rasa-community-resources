#!/usr/bin/env python3
"""Unit tests for the ASR benchmark. No network, no credentials, no models.

Everything here is arithmetic over strings or a decision about what may be
printed. The parts that need a vendor — actually transcribing audio — are not
tested here, because a test that needed a vendor could not run in CI, which is
exactly the property the benchmark itself is built around.

    make test
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from voicerouter.bench import (  # noqa: E402
    BenchReport,
    Fixture,
    Observation,
    edit_distance,
    normalise,
    similarity,
    word_error_rate,
)


class TestNormalisation(unittest.TestCase):
    """Vendors punctuate to their own house style; that is not disagreement."""

    def test_case_and_punctuation_are_not_content(self):
        self.assertEqual(normalise("Yes, that is correct."), "yes that is correct")

    def test_whitespace_runs_collapse(self):
        self.assertEqual(normalise("  yes   that\tis  "), "yes that is")

    def test_apostrophes_survive(self):
        # "dont" and "don't" are the same word; splitting it would invent a
        # disagreement between a vendor that punctuates and one that does not.
        self.assertEqual(normalise("I don't know"), "i don't know")

    def test_none_and_empty_are_safe(self):
        self.assertEqual(normalise(""), "")
        self.assertEqual(normalise(None), "")


class TestEditDistance(unittest.TestCase):
    def test_identical_sequences_are_zero(self):
        self.assertEqual(edit_distance(["a", "b"], ["a", "b"]), 0)

    def test_empty_against_full_is_the_length(self):
        self.assertEqual(edit_distance([], ["a", "b", "c"]), 3)
        self.assertEqual(edit_distance(["a", "b", "c"], []), 3)

    def test_substitution_insertion_and_deletion_each_cost_one(self):
        self.assertEqual(edit_distance(["a", "b"], ["a", "c"]), 1)
        self.assertEqual(edit_distance(["a"], ["a", "b"]), 1)
        self.assertEqual(edit_distance(["a", "b"], ["a"]), 1)


class TestAgreement(unittest.TestCase):
    """Agreement is the only quality signal the engine makes available."""

    def test_identical_transcripts_agree_completely(self):
        self.assertEqual(similarity("hello there", "hello there"), 1.0)

    def test_agreement_ignores_style_differences(self):
        self.assertEqual(similarity("Yes, that is correct.", "yes that is correct"), 1.0)

    def test_disagreement_is_proportional(self):
        # One token of four differs.
        self.assertAlmostEqual(similarity("a b c d", "a b c e"), 0.75)

    def test_nothing_in_common_is_zero(self):
        self.assertEqual(similarity("alpha", "beta"), 0.0)

    def test_two_silences_agree_rather_than_dividing_by_zero(self):
        # Both vendors heard nothing. That is a real agreement, and the naive
        # implementation raises here instead.
        self.assertEqual(similarity("", ""), 1.0)

    def test_agreement_is_symmetric(self):
        a, b = "transfer two hundred pounds", "transfer two hundred and fifty"
        self.assertEqual(similarity(a, b), similarity(b, a))


class TestWordErrorRate(unittest.TestCase):
    def test_perfect_transcript_scores_zero(self):
        self.assertEqual(word_error_rate("yes that is correct", "Yes, that is correct."), 0.0)

    def test_one_wrong_word_in_four(self):
        self.assertAlmostEqual(word_error_rate("a b c d", "a b c e"), 0.25)

    def test_hallucination_may_exceed_one_and_is_not_clamped(self):
        # A vendor that invents a paragraph over a two-word utterance is worse
        # than one that returns nothing, and the number must be able to say so.
        self.assertGreater(word_error_rate("yes please", "yes please " + "x " * 10), 1.0)

    def test_an_empty_reference_is_refused_not_scored(self):
        # Scoring against no reference is the fabrication this benchmark must
        # never commit, so it raises rather than returning a plausible 0.0.
        with self.assertRaises(ValueError):
            word_error_rate("", "anything at all")


def _report(with_reference: bool = True) -> BenchReport:
    """Two adapters over two fixtures, agreeing on one and differing on one."""
    fixtures = [
        Fixture("greeting", reference="hello there" if with_reference else None),
        Fixture("digits", reference="four eight one" if with_reference else None),
    ]
    report = BenchReport(fixtures=fixtures)
    for label, greeting, digits in (
        ("vosk", "hello there", "four eight one"),
        ("whisper", "hello there", "four eight nine"),
    ):
        report.observations.append(Observation("greeting", label, greeting, 100.0))
        report.observations.append(Observation("digits", label, digits, 120.0))
    return report


class TestAgreementMatrix(unittest.TestCase):
    def test_an_adapter_agrees_with_itself(self):
        matrix = _report().agreement_matrix()
        self.assertEqual(matrix[("vosk", "vosk")], 1.0)

    def test_the_matrix_is_symmetric(self):
        matrix = _report().agreement_matrix()
        self.assertEqual(matrix[("vosk", "whisper")], matrix[("whisper", "vosk")])

    def test_partial_disagreement_lands_between_zero_and_one(self):
        # Agree on one fixture, differ by one token of three on the other.
        score = _report().agreement_matrix()[("vosk", "whisper")]
        self.assertAlmostEqual(score, (1.0 + 2 / 3) / 2)

    def test_a_pair_that_never_shared_a_fixture_is_none_not_zero(self):
        """Never compared is not the same as compared and found different."""
        report = BenchReport(fixtures=[Fixture("a"), Fixture("b")])
        report.observations.append(Observation("a", "vosk", "hello", 10.0))
        report.observations.append(Observation("b", "whisper", "hello", 10.0))
        self.assertIsNone(report.agreement_matrix()[("vosk", "whisper")])

    def test_a_failed_call_does_not_count_as_a_transcript(self):
        report = BenchReport(fixtures=[Fixture("a")])
        report.observations.append(Observation("a", "vosk", "hello", 10.0))
        report.observations.append(
            Observation("a", "whisper", "", 10.0, error="RuntimeError: boom")
        )
        self.assertIsNone(report.agreement_matrix()[("vosk", "whisper")])

    def test_hotspots_rank_the_worst_fixture_first(self):
        hotspots = _report().disagreement_hotspots()
        self.assertEqual(hotspots[0][0], "digits")

    def test_a_fixture_only_one_adapter_heard_is_not_a_hotspot(self):
        # One transcript cannot disagree with anything, and listing it at 0.00
        # would send an operator to listen to perfectly good audio.
        report = BenchReport(fixtures=[Fixture("lonely")])
        report.observations.append(Observation("lonely", "vosk", "hello", 10.0))
        self.assertEqual(report.disagreement_hotspots(), [])


class TestLatency(unittest.TestCase):
    def test_distribution_is_reported_over_successful_calls(self):
        d = _report().latency("vosk")
        self.assertEqual(d["n"], 2)
        self.assertEqual(d["min"], 100.0)
        self.assertEqual(d["max"], 120.0)

    def test_a_failed_call_is_not_a_latency_sample(self):
        """How long a vendor took to say no is a different quantity."""
        report = BenchReport(fixtures=[Fixture("a"), Fixture("b")])
        report.observations.append(Observation("a", "vosk", "hi", 100.0))
        report.observations.append(
            Observation("b", "vosk", "", 9000.0, error="TimeoutError")
        )
        d = report.latency("vosk")
        self.assertEqual(d["n"], 1)
        self.assertEqual(d["max"], 100.0)

    def test_an_adapter_that_never_succeeded_has_no_distribution(self):
        report = BenchReport(fixtures=[Fixture("a")])
        report.observations.append(
            Observation("a", "vosk", "", 10.0, error="RuntimeError: boom")
        )
        self.assertEqual(report.latency("vosk"), {})


class TestWerOnlyWhenReferenceExists(unittest.TestCase):
    """The non-goal with teeth: never fabricate a ground truth."""

    def test_wer_is_computed_when_references_are_present(self):
        report = _report(with_reference=True)
        self.assertTrue(report.has_references)
        self.assertEqual(report.wer("vosk"), 0.0)
        self.assertAlmostEqual(report.wer("whisper"), (0.0 + 1 / 3) / 2)

    def test_wer_is_absent_entirely_when_no_fixture_has_a_reference(self):
        report = _report(with_reference=False)
        self.assertFalse(report.has_references)
        self.assertIsNone(report.wer("vosk"))
        self.assertIsNone(report.wer("whisper"))

    def test_agreement_still_works_without_any_reference(self):
        # The whole point of agreement: it needs no ground truth, so an
        # unlabelled corpus of real caller audio still produces a signal.
        report = _report(with_reference=False)
        self.assertIsNotNone(report.agreement_matrix()[("vosk", "whisper")])
        self.assertEqual(report.disagreement_hotspots()[0][0], "digits")

    def test_a_partially_referenced_corpus_scores_only_the_referenced_part(self):
        report = BenchReport(fixtures=[
            Fixture("known", reference="hello there"),
            Fixture("unknown"),
        ])
        report.observations.append(Observation("known", "vosk", "hello there", 10.0))
        report.observations.append(Observation("unknown", "vosk", "anything", 10.0))
        self.assertTrue(report.has_references)
        self.assertEqual(report.wer("vosk"), 0.0)


class TestSkipPath(unittest.TestCase):
    """An unreachable adapter is skipped and reported — never a failure."""

    def test_an_unreachable_adapter_is_recorded_with_its_reason(self):
        report = BenchReport(fixtures=[Fixture("a")])
        report.skipped["azure"] = "no AZURE_SPEECH_API_KEY — not configured here"
        self.assertIn("azure", report.skipped)
        self.assertNotIn("azure", report.labels)

    def test_a_report_where_everything_was_skipped_is_still_valid(self):
        """The default run on a machine with no credentials and no local models.

        This must produce an empty measurement rather than raising, because it
        is the outcome on any CI runner.
        """
        report = BenchReport(fixtures=[Fixture("a")])
        report.skipped["deepgram"] = "no DEEPGRAM_API_KEY — not configured here"
        report.skipped["vosk-local"] = "vosk is not installed"
        self.assertEqual(report.labels, [])
        self.assertEqual(report.agreement_matrix(), {})
        self.assertEqual(report.disagreement_hotspots(), [])
        self.assertEqual(report.latency("vosk-local"), {})

    def test_cloud_adapters_are_not_in_the_default_local_allowlist(self):
        """The invariant, as an assertion: the default run cannot bill anyone.

        Only adapters that execute on this machine may run by default. If a
        vendor is ever added to this set, it must be because it is genuinely
        local — this test is the place that decision gets noticed.
        """
        from bench_asr import LOCAL_ASR_PATHS

        self.assertEqual(
            LOCAL_ASR_PATHS,
            {
                "voicerouter.providers.vosk.VoskASR",
                "voicerouter.providers.whisper.FasterWhisperASR",
            },
        )
        for path in LOCAL_ASR_PATHS:
            self.assertNotIn("aws", path.lower())
            self.assertNotIn("google", path.lower())


class TestFixtureCorpus(unittest.TestCase):
    """The committed corpus has to stay replayable and licence-clean."""

    def setUp(self):
        self.corpus = Path(__file__).resolve().parent / "fixtures" / "audio"

    def test_the_manifest_and_the_audio_agree(self):
        import json

        manifest = json.loads((self.corpus / "manifest.json").read_text())
        self.assertTrue(manifest["utterances"], "corpus is empty")
        for entry in manifest["utterances"]:
            with self.subTest(fixture=entry["name"]):
                self.assertTrue((self.corpus / entry["audio"]).is_file())
                self.assertTrue(entry["reference"].strip())

    def test_every_clip_is_a_riff_wave(self):
        for wav in self.corpus.glob("*.wav"):
            with self.subTest(wav=wav.name):
                head = wav.read_bytes()[:12]
                self.assertEqual(head[:4], b"RIFF")
                self.assertEqual(head[8:12], b"WAVE")

    def test_the_corpus_stays_small(self):
        """A demonstration fixture, not a dataset. Guard against drift."""
        total = sum(w.stat().st_size for w in self.corpus.glob("*.wav"))
        self.assertLess(total, 4_000_000, "fixture corpus is growing into a dataset")


if __name__ == "__main__":
    unittest.main(verbosity=2)
