#!/usr/bin/env python3
"""Eval suite for the handoff context package. No network, no model, no license.

Two tests are required by the pattern's charter and the second is the
load-bearing one:

  (a) THE PACKAGE SURVIVES A HANDOFF INTACT — everything the agent established
      is still there on the far side of a serialise/deliver/receive round trip,
      and the desk can reconstruct the caller's state from it alone.

  (b) A SENSITIVE FIELD DELIBERATELY PLACED IN SESSION STATE DOES NOT REACH THE
      PACKAGE — not in any field, not in the summary, not in the JSON that
      crosses the boundary.

Test (b) has been verified to FAIL when the allowlist is removed. The procedure
and the observed failure are recorded in the README under "Proving the guard
fails". A guard nobody has watched go red is a docstring, not a guard.

    make test
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handoffpkg.desk import (  # noqa: E402
    DESK_OPENING_SCRIPT,
    deliver,
    permitted_actions,
    receive,
    reconstruct,
    unanswered_questions,
)
from handoffpkg.redaction import (  # noqa: E402
    SESSION_ALLOWLIST,
    build_package_from_session,
    filter_session,
    scan_freetext_risk,
)
from handoffpkg.schema import (  # noqa: E402
    HandoffPackage,
    Identity,
    Intent,
    normalise_tier,
    package_from_dict,
    tier_at_least,
)

# ---------------------------------------------------------------------------
# The session state under test.
# ---------------------------------------------------------------------------
# Deliberately mixed: allowlisted business fields sit next to credentials that a
# real skill genuinely would have written. `pin_attempt` is not invented for
# this test — it is the exact field name used by
# examples/mantle-voice-agent/skills/authenticate/memory.yml, which is
# llm_settable and holds the caller's spoken PIN. If this pattern's boundary
# does not stop that field, it does not stop the one that actually exists.

SENSITIVE_VALUES = {
    "pin_attempt": "4242",
    "otp_code": "889134",
    "card_number": "4111111111111111",
    "passphrase_attempt": "harbour lighthouse",
    "auth_token": "tok_live_51H8xQe",
    "recording_url": "https://recordings.internal/call/9931.wav",
    "ssn": "123-45-6789",
}


def demo_session() -> dict:
    """Session state at the moment the caller asks for a human."""
    session = {
        # --- allowlisted: the state that SHOULD cross -----------------------
        "customer_id": "cust_00417",
        "display_name": "Jordan Rivera",
        "verified_tier": "medium",
        "verified_factors": ["knowledge_passphrase"],
        "channel": "voice:+1-555-0100",
        "goal": "dispute_transaction",
        "goal_label": "Dispute a card transaction",
        "goal_stage": "blocked",
        "account_id": "acc_checking",
        "account_label": "Everyday Checking",
        "card_last_four": "4821",
        "dispute_amount": "$248.00",
        "dispute_merchant": "Northgate Fuel",
        "dispute_date": "2026-08-29",
        "handoff_reason": "Dispute needs a second factor the caller cannot complete on this line.",
        "attempts": [
            {
                "action": "verify_passphrase",
                "outcome": "succeeded",
                "detail": "Caller answered the knowledge factor correctly on the first try.",
            },
            {
                "action": "send_otp_sms",
                "outcome": "failed",
                "code": "delivery_failed",
                "detail": "Carrier rejected the SMS twice. Do not resend to this number.",
            },
            {
                "action": "raise_dispute",
                "outcome": "blocked",
                "code": "insufficient_tier",
                "detail": "Dispute needs tier 'high'; caller is at 'medium'.",
            },
        ],
        "questions_answered": (
            "Can I take your name?",
            "Can you confirm your date of birth?",
            "Which account is this about?",
            "What are you calling about today?",
            "Have you tried anything already?",
        ),
        "factors_verified": ("knowledge_passphrase",),
        "confirmed_facts": ("Caller consented to the call being recorded.",),
    }
    # --- NOT allowlisted: the state that MUST NOT cross ---------------------
    session.update(SENSITIVE_VALUES)
    return session


class TestPackageSurvivesHandoff(unittest.TestCase):
    """(a) Everything the agent established is still there on the far side."""

    def setUp(self):
        self.package = build_package_from_session(demo_session(), handoff_id="ho_0001")

    def test_identity_and_tier_cross_together(self):
        """A name without its tier is how a desk trusts an unverified caller."""
        self.assertEqual(self.package.identity.customer_id, "cust_00417")
        self.assertEqual(self.package.identity.display_name, "Jordan Rivera")
        self.assertEqual(self.package.identity.verified_tier, "medium")
        self.assertEqual(self.package.identity.verified_factors, ("knowledge_passphrase",))

    def test_intent_is_structured_not_prose(self):
        """`goal` is an identifier a desk can route on, not a sentence."""
        self.assertEqual(self.package.intent.goal, "dispute_transaction")
        self.assertEqual(self.package.intent.stage, "blocked")
        self.assertEqual(self.package.intent.details["account_id"], "acc_checking")
        self.assertEqual(self.package.intent.details["dispute_amount"], "$248.00")

    def test_failed_attempts_carry_their_outcome(self):
        """The human must not resend an SMS the carrier already rejected twice."""
        by_action = {a.action: a for a in self.package.attempts}
        self.assertEqual(by_action["send_otp_sms"].outcome, "failed")
        self.assertEqual(by_action["send_otp_sms"].code, "delivery_failed")
        self.assertEqual(by_action["raise_dispute"].outcome, "blocked")
        self.assertEqual(by_action["verify_passphrase"].outcome, "succeeded")

    def test_round_trip_through_the_boundary_loses_nothing(self):
        """Deliver to a queue, read it back, and compare field by field."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "handoff.json")
            deliver(self.package, path)
            restored = package_from_dict(json.loads(Path(path).read_text()))

        self.assertEqual(restored.identity, self.package.identity)
        self.assertEqual(restored.intent, self.package.intent)
        self.assertEqual(restored.attempts, self.package.attempts)
        self.assertEqual(restored.do_not_repeat, self.package.do_not_repeat)
        self.assertEqual(restored.withheld_fields, self.package.withheld_fields)

    def test_desk_reconstructs_the_callers_state(self):
        """The receiving side, given ONLY the package, rebuilds who/what/tried."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "handoff.json")
            deliver(self.package, path)
            view = receive(path)

        self.assertIn("Jordan Rivera", view.caller)
        self.assertIn("cust_00417", view.caller)
        self.assertIn("medium", view.trust)
        self.assertIn("Dispute a card transaction", view.asking_for)
        self.assertTrue(any("send_otp_sms" in item for item in view.already_tried))
        self.assertTrue(any("failed" in item for item in view.already_tried))

    def test_caller_is_never_asked_a_question_they_answered(self):
        """The teaching claim, as a number rather than a sentence."""
        self.assertEqual(unanswered_questions(self.package), ())

    def test_the_catalogs_current_handoff_answers_nothing(self):
        """Baseline: one free-text reason retires none of the desk's questions.

        This is what every example in the catalog ships today — a
        `handoff_reason` string and a ticket id. Asserting it here is what makes
        the improvement measurable rather than asserted.
        """
        today = build_package_from_session(
            {"handoff_reason": "Caller wants to speak to a person."},
            handoff_id="ho_today",
        )
        self.assertEqual(len(unanswered_questions(today)), len(DESK_OPENING_SCRIPT))

    def test_desk_permissions_follow_the_tier_not_the_package(self):
        """A medium-tier caller must not be actioned for an irreversible change."""
        actions = permitted_actions(self.package)
        self.assertTrue(any("Discuss account-specific details" == a for a in actions))
        self.assertTrue(any(a.startswith("DO NOT action irreversible") for a in actions))


class TestSensitiveFieldsNeverCross(unittest.TestCase):
    """(b) THE LOAD-BEARING TEST.

    A sensitive field placed in session state must not reach the package — in
    any field, in the summary, or in the JSON that crosses the boundary.

    Verified to go RED when SESSION_ALLOWLIST is bypassed; see the README
    section "Proving the guard fails" for the exact edit and the output.
    """

    def setUp(self):
        self.session = demo_session()
        self.package = build_package_from_session(self.session, handoff_id="ho_0002")
        self.serialised = json.dumps(self.package.to_dict(), sort_keys=True)

    def test_no_sensitive_value_appears_anywhere_in_the_package(self):
        """The whole serialised package, searched for every planted value."""
        for name, value in SENSITIVE_VALUES.items():
            with self.subTest(field=name):
                self.assertNotIn(
                    value,
                    self.serialised,
                    f"{name} leaked into the package: {value!r} found in the payload "
                    f"that crosses to the human agent",
                )

    def test_no_sensitive_value_appears_in_the_derived_summary(self):
        """The summary is derived, so it inherits the boundary — prove it does."""
        summary = self.package.summary
        for name, value in SENSITIVE_VALUES.items():
            with self.subTest(field=name):
                self.assertNotIn(value, summary, f"{name} leaked into the summary")

    def test_no_sensitive_value_reaches_the_rendered_desk_screen(self):
        """The last surface: what the human actually reads on their monitor."""
        screen = reconstruct(self.package).render()
        for name, value in SENSITIVE_VALUES.items():
            with self.subTest(field=name):
                self.assertNotIn(value, screen, f"{name} leaked onto the desk screen")

    def test_withheld_names_cross_but_values_do_not(self):
        """The desk learns a PIN exists and was withheld; it never learns the PIN.

        This is the deliberate asymmetry. Without the name the desk asks the
        caller to repeat a credential the system already holds; with the value
        the credential has been copied to a new surface. The name is the whole
        of what is useful.
        """
        withheld = set(self.package.withheld_fields)
        for name in SENSITIVE_VALUES:
            self.assertIn(name, withheld, f"{name} was silently dropped, not announced")
        self.assertNotIn(SENSITIVE_VALUES["pin_attempt"], self.serialised)

    def test_a_field_nobody_anticipated_is_withheld_by_default(self):
        """The allowlist's real job: the field added next sprint, unreviewed.

        A denylist would pass this test today and fail it the moment someone
        writes a new key. This asserts the default, which is the property that
        makes an allowlist worth the friction.
        """
        session = demo_session()
        session["biometric_voiceprint_hash"] = "vp_9f2a41c7b0"
        session["mothers_maiden_name"] = "Castellanos"
        package = build_package_from_session(session, handoff_id="ho_0003")
        payload = json.dumps(package.to_dict())
        self.assertNotIn("vp_9f2a41c7b0", payload)
        self.assertNotIn("Castellanos", payload)
        self.assertIn("biometric_voiceprint_hash", package.withheld_fields)
        self.assertIn("mothers_maiden_name", package.withheld_fields)

    def test_filter_session_returns_no_value_for_a_withheld_key(self):
        """Not masked, not hashed, not truncated — absent. Masked values leak."""
        allowed, withheld = filter_session(demo_session())
        for name in SENSITIVE_VALUES:
            self.assertNotIn(name, allowed)
            self.assertIn(name, withheld)

    def test_allowlist_does_not_contain_any_credential_key(self):
        """Guards the allowlist itself against a careless future addition."""
        for name in SENSITIVE_VALUES:
            self.assertNotIn(
                name,
                SESSION_ALLOWLIST,
                f"{name} was added to SESSION_ALLOWLIST — that is a policy change, "
                f"not a refactor",
            )


class TestTheAgentPathSpecifically(unittest.TestCase):
    """The credentials the RUNNING AGENT collects, through the agent's own list.

    The tests above plant credentials in a synthetic session. These use the
    exact key list `skills/human_handoff/tools.py` reads from live memory, so a
    future edit that trims that list — or that adds a credential to it without
    adding it to the allowlist — is caught here rather than in production.
    """

    def _agent_memory_keys(self) -> tuple[str, ...]:
        """Read _MEMORY_KEYS out of the tool module without importing rasa.

        The tool module imports `rasa.mantle`, which the eval suite deliberately
        does not depend on — `make test` runs with no license and no install.
        Parsing the literal keeps this test honest about the real list while
        staying offline.
        """
        source = (
            Path(__file__).resolve().parents[1]
            / "skills" / "human_handoff" / "tools.py"
        ).read_text()
        block = source.split("_MEMORY_KEYS = (", 1)[1].split(")", 1)[0]
        return tuple(
            line.strip().strip(",").strip('"')
            for line in block.splitlines()
            if line.strip().startswith('"')
        )

    def test_the_agent_collects_credentials_and_the_allowlist_stops_them(self):
        """End to end on the real key list: collected, then withheld."""
        keys = self._agent_memory_keys()
        self.assertIn("pin_attempt", keys, "the agent no longer collects pin_attempt — "
                                           "the allowlist is then untested on this path")
        self.assertIn("otp_code", keys)

        session = {key: SENSITIVE_VALUES.get(key, f"value_for_{key}") for key in keys}
        package = build_package_from_session(session, handoff_id="ho_agent")
        payload = json.dumps(package.to_dict())

        self.assertNotIn(SENSITIVE_VALUES["pin_attempt"], payload)
        self.assertNotIn(SENSITIVE_VALUES["otp_code"], payload)
        self.assertIn("pin_attempt", package.withheld_fields)
        self.assertIn("otp_code", package.withheld_fields)

    def test_the_agent_path_retires_every_desk_question(self):
        """THE HEADLINE CLAIM, ON THE PATH THE AGENT ACTUALLY RUNS.

        This test exists because the claim once passed while being false. The
        eval suite built its own session dict containing `account_id`, so
        `intent.details` was populated and "which account is this about?" was
        retired — but the agent's own `_MEMORY_KEYS` did not collect
        `account_id`, so a real handoff shipped an empty `details` and the desk
        asked anyway. Green tests, broken claim.

        The fix is to drive the assertion from the SAME two lists the agent uses:
        the keys the handoff tool collects, and the memory the dispute skill
        writes. A future edit that drops a key from either one fails here.
        """
        written = self._skill_memory_writes()
        collected = self._agent_memory_keys()

        # Every detail key the allowlist expects must be both written by a skill
        # and collected by the handoff tool, or it never reaches the package.
        for key in ("account_id", "account_label", "card_last_four"):
            with self.subTest(key=key):
                self.assertIn(key, written, f"no skill writes {key} to memory")
                self.assertIn(key, collected, f"the handoff tool does not collect {key}")

        # Now build a session from ONLY what the agent genuinely produces.
        session = {key: f"value_for_{key}" for key in collected if key in written}
        session["verified_tier"] = "medium"
        session["goal"] = "dispute_transaction"
        session["questions_answered"] = "\n".join(DESK_OPENING_SCRIPT)
        session["attempts"] = [
            {"action": "send_otp_sms", "outcome": "failed", "code": "delivery_failed"}
        ]
        package = build_package_from_session(session, handoff_id="ho_live")

        self.assertTrue(package.intent.details.get("account_id"),
                        "intent.details is empty on the live path — the desk will "
                        "re-ask which account this is about")
        self.assertEqual(
            unanswered_questions(package), (),
            "the caller would be re-asked a question they already answered",
        )

    def _skill_memory_writes(self) -> set:
        """Memory keys the dispute skill's tools actually write.

        Parsed from source rather than imported: the tool module imports
        `rasa.mantle`, and `make test` runs with no install and no license.
        """
        source = (
            Path(__file__).resolve().parents[1]
            / "skills" / "dispute_transaction" / "tools.py"
        ).read_text()
        keys = set(re.findall(r'memory\.set\(\s*"([^"]+)"', source))
        keys |= set(re.findall(r'_append\(\s*context,\s*"([^"]+)"', source))
        # The `for key in (...)` loop that writes the caller profile.
        for block in re.findall(r"for key in \(([^)]*)\):", source):
            keys |= set(re.findall(r'"([^"]+)"', block))
        return keys

    def test_every_key_the_agent_collects_is_either_allowlisted_or_withheld(self):
        """No third category. A key is a decision, and both outcomes are visible."""
        keys = self._agent_memory_keys()
        session = {key: f"value_for_{key}" for key in keys}
        package = build_package_from_session(session, handoff_id="ho_agent2")
        for key in keys:
            with self.subTest(key=key):
                self.assertTrue(
                    key in SESSION_ALLOWLIST or key in package.withheld_fields,
                    f"{key} is collected by the agent but is neither allowlisted "
                    f"nor reported as withheld",
                )


class TestStatedLimits(unittest.TestCase):
    """The allowlist's limits, asserted so the README cannot overclaim.

    RULING-007 landed because a repository asserted a property nothing checked.
    The inverse discipline applies here: the README says the allowlist does NOT
    police free text, and that statement is tested too — a claim about a
    limitation is still a claim.
    """

    def test_freetext_in_an_allowlisted_field_is_transferred_verbatim(self):
        """The documented hole, demonstrated rather than hedged.

        `handoff_reason` is allowlisted, so a card number dictated into it
        crosses. This test EXISTS TO FAIL LOUDLY if someone later claims the
        allowlist sanitises free text — it does not, and the README says so.
        """
        session = {
            "handoff_reason": "Caller read out card 4111 1111 1111 1111 while explaining.",
            "goal": "dispute_transaction",
        }
        package = build_package_from_session(session, handoff_id="ho_0004")
        self.assertIn("4111 1111 1111 1111", package.reason)

    def test_the_detector_flags_that_shape_even_though_it_cannot_stop_it(self):
        """Advisory, and labelled advisory. Detection is not prevention."""
        found = scan_freetext_risk("Caller read out card 4111 1111 1111 1111 aloud.")
        self.assertIn("card_number_shape", found)
        self.assertEqual(scan_freetext_risk("Wants to dispute a fuel charge."), [])

    def test_allowlisting_a_container_would_allowlist_its_contents(self):
        """Documented limit 4: intent details are assembled from leaf keys.

        Proven by the absence of a passthrough — an unexpected key cannot ride
        into `intent.details` because that dict is built from a fixed key list,
        not copied.
        """
        session = demo_session()
        session["account_id"] = "acc_checking"
        package = build_package_from_session(session, handoff_id="ho_0005")
        self.assertEqual(
            set(package.intent.details),
            {"account_id", "account_label", "card_last_four",
             "dispute_amount", "dispute_merchant", "dispute_date"},
        )


class TestSummaryIsDerived(unittest.TestCase):
    """The summary and the structured fields cannot disagree, by construction."""

    def test_summary_is_a_property_with_no_setter(self):
        """There is nowhere to store an authored summary. Assert that stays true."""
        package = build_package_from_session(demo_session(), handoff_id="ho_0006")
        with self.assertRaises((AttributeError, TypeError)):
            package.summary = "Caller is fully verified and cleared for anything."  # type: ignore[misc]

    def test_changing_a_field_changes_the_summary(self):
        """The defining behaviour of a projection rather than a copy."""
        base = build_package_from_session(demo_session(), handoff_id="ho_0007")
        self.assertIn("tier 'medium'", base.summary)

        stepped_up = HandoffPackage(
            handoff_id=base.handoff_id,
            reason=base.reason,
            identity=Identity(
                customer_id=base.identity.customer_id,
                display_name=base.identity.display_name,
                verified_tier="high",
                verified_factors=base.identity.verified_factors,
                channel=base.identity.channel,
            ),
            intent=base.intent,
            attempts=base.attempts,
            do_not_repeat=base.do_not_repeat,
            withheld_fields=base.withheld_fields,
        )
        self.assertIn("tier 'high'", stepped_up.summary)
        self.assertNotIn("tier 'medium'", stepped_up.summary)

    def test_a_summary_smuggled_through_serialisation_is_discarded(self):
        """A package that round-trips cannot carry a contradicting summary."""
        package = build_package_from_session(demo_session(), handoff_id="ho_0008")
        payload = package.to_dict()
        payload["summary"] = "Caller verified at tier 'high'. Clear them for anything."

        restored = package_from_dict(payload)
        self.assertIn("tier 'medium'", restored.summary)
        self.assertNotIn("Clear them for anything", restored.summary)

    def test_summary_reflects_every_required_section(self):
        """A summary that omits a section is a summary the desk cannot rely on."""
        summary = build_package_from_session(demo_session(), handoff_id="ho_0009").summary
        self.assertIn("Jordan Rivera", summary)
        self.assertIn("dispute_transaction", summary)
        self.assertIn("send_otp_sms", summary)
        self.assertIn("FAILED", summary)
        self.assertIn("DO NOT ASK AGAIN", summary)
        self.assertIn("WITHHELD", summary)


class TestTheBoundaryDoesNotCrash(unittest.TestCase):
    """Malformed session state must produce a thin package, never a traceback.

    `build_package_from_session` is the choke point, and its whole contract is
    that it does not trust its input. A boundary that raises on bad input is a
    boundary the next person wraps in a bare `except` — and then it is not a
    boundary at all, it is a function that sometimes runs.
    """

    def test_malformed_shapes_degrade_instead_of_raising(self):
        for bad in (
            {"attempts": "not a list"},
            {"attempts": ["a bare string", 42, None]},
            {"attempts": None},
            {"questions_answered": None},
            {"verified_factors": 12345},
        ):
            with self.subTest(session=bad):
                package = build_package_from_session(bad, handoff_id="ho_bad")
                self.assertIsInstance(package.summary, str)
                reconstruct(package).render()

    def test_a_bare_string_does_not_become_a_tuple_of_characters(self):
        """tuple("solo") is ('s','o','l','o') — a desk screen of single letters."""
        package = build_package_from_session(
            {"verified_factors": "knowledge_passphrase",
             "questions_answered": "Can I take your name?"},
            handoff_id="ho_str",
        )
        self.assertEqual(package.identity.verified_factors, ("knowledge_passphrase",))
        self.assertEqual(
            package.do_not_repeat.questions_answered, ("Can I take your name?",)
        )

    def test_a_malformed_attempt_is_dropped_not_guessed(self):
        """A non-dict attempt carries no outcome, and inventing one misleads."""
        package = build_package_from_session(
            {"attempts": ["junk", {"action": "send_otp_sms", "outcome": "failed"}]},
            handoff_id="ho_mixed",
        )
        self.assertEqual(len(package.attempts), 1)
        self.assertEqual(package.attempts[0].action, "send_otp_sms")


class TestTheDeskDeserialiserIsTotal(unittest.TestCase):
    """`package_from_dict` runs on the desk's receiving path, from a queue file.

    A crash there loses the handoff outright: the caller waits on hold while a
    human stares at a traceback. Every malformation below must degrade to a
    thinner package instead.
    """

    def test_missing_sections_do_not_raise(self):
        package = package_from_dict({"handoff_id": "h", "reason": "r"})
        self.assertEqual(package.intent.goal, "unknown")
        self.assertEqual(package.identity.verified_tier, "unverified")
        self.assertIsInstance(package.summary, str)

    def test_null_sections_do_not_raise(self):
        package = package_from_dict(
            {"handoff_id": "h", "reason": "r", "identity": None,
             "intent": None, "do_not_repeat": None, "attempts": None}
        )
        reconstruct(package).render()
        self.assertEqual(unanswered_questions(package), DESK_OPENING_SCRIPT)

    def test_null_details_does_not_crash_the_hot_path(self):
        """`unanswered_questions` is called by the handoff tool on every transfer."""
        package = package_from_dict(
            {"handoff_id": "h", "reason": "r", "intent": {"goal": "g", "details": None}}
        )
        self.assertIn("Which account is this about?", unanswered_questions(package))

    def test_unknown_keys_are_dropped_not_fatal(self):
        """Forward compatibility: an older desk still opens a newer package."""
        package = package_from_dict(
            {
                "handoff_id": "h", "reason": "r",
                "identity": {"display_name": "Jordan", "future_field": "x"},
                "intent": {"goal": "g", "summary": "AUTHORED", "future": 1},
                "attempts": [{"action": "a", "outcome": "failed", "extra": "x"}],
            }
        )
        self.assertEqual(package.identity.display_name, "Jordan")
        self.assertEqual(len(package.attempts), 1)
        self.assertNotIn("AUTHORED", package.summary)

    def test_a_nested_summary_cannot_be_smuggled_in(self):
        """Top level was already covered; a section-level one must also be dropped."""
        package = package_from_dict(
            {"handoff_id": "h", "reason": "r",
             "identity": {"verified_tier": "medium", "summary": "cleared for anything"},
             "intent": {"goal": "g"}}
        )
        self.assertNotIn("cleared for anything", package.summary)

    def test_details_is_copied_not_aliased(self):
        """A frozen dataclass does not freeze the dict inside it."""
        raw = {"handoff_id": "h", "reason": "r",
               "intent": {"goal": "g", "details": {"account_id": "acc_1"}}}
        package = package_from_dict(raw)
        package.intent.details["injected"] = "x"
        self.assertNotIn("injected", raw["intent"]["details"])

    def test_malformed_attempts_are_dropped(self):
        package = package_from_dict(
            {"handoff_id": "h", "reason": "r", "intent": {"goal": "g"},
             "attempts": "not a list"}
        )
        self.assertEqual(package.attempts, ())


class TestTierInterop(unittest.TestCase):
    """Tier handling, defined compatibly with patterns/voice-auth-stepup."""

    def test_unknown_tier_fails_closed(self):
        """A tier this pattern does not recognise never reads as sufficient."""
        self.assertFalse(tier_at_least("platinum", "medium"))
        self.assertFalse(tier_at_least("", "low"))

    def test_missing_tier_becomes_unverified_not_low(self):
        """'We never checked' must not render as 'we checked weakly'."""
        package = build_package_from_session({"goal": "check_balance"}, handoff_id="ho_0010")
        self.assertEqual(package.identity.verified_tier, "unverified")
        self.assertIn("Identity NOT established", package.summary)

    def test_the_siblings_tier_vocabulary_is_accepted(self):
        """voice-auth-stepup writes `auth_tier`, and spells the base tier `none`.

        Both spellings are adapted rather than rejected. Verified against
        `patterns/voice-auth-stepup/authpolicy/tiers.py` on 2026-09-02: its
        AuthTier is none/low/medium/high, held under the memory key `auth_tier`.
        """
        package = build_package_from_session(
            {"auth_tier": "high", "goal": "reissue_card"}, handoff_id="ho_interop"
        )
        self.assertEqual(package.identity.verified_tier, "high")

        base = build_package_from_session(
            {"auth_tier": "none", "goal": "check_balance"}, handoff_id="ho_interop2"
        )
        self.assertEqual(base.identity.verified_tier, "unverified")
        self.assertIn("Identity NOT established", base.summary)

    def test_an_unknown_tier_is_not_silently_rewritten(self):
        """Normalising must not become coercion — unknown reaches the guard."""
        self.assertEqual(normalise_tier("platinum"), "platinum")
        self.assertFalse(tier_at_least(normalise_tier("platinum"), "low"))

    def test_disagreeing_tier_spellings_resolve_to_the_WEAKER(self):
        """Both spellings present and disagreeing: take the weaker, both ways.

        Over-stating a caller's strength hands a human the authority to action an
        irreversible change for someone never verified to that level. Under-
        stating it costs one step-up. Only one of those is an incident.
        """
        for session, expected in (
            ({"verified_tier": "low", "auth_tier": "high"}, "low"),
            ({"verified_tier": "high", "auth_tier": "low"}, "low"),
            ({"verified_tier": "none", "auth_tier": "high"}, "unverified"),
            ({"verified_tier": "high", "auth_tier": "none"}, "unverified"),
        ):
            with self.subTest(session=session):
                package = build_package_from_session(session, handoff_id="ho_t")
                self.assertEqual(package.identity.verified_tier, expected)

    def test_ordering_matches_the_sibling_patterns_tiers(self):
        self.assertTrue(tier_at_least("high", "medium"))
        self.assertTrue(tier_at_least("medium", "medium"))
        self.assertFalse(tier_at_least("low", "medium"))
        self.assertFalse(tier_at_least("unverified", "low"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
