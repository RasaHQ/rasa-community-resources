#!/usr/bin/env python3
"""The eval suite for the tier guard. No network, no model, no credentials.

    make test

WHICH TEST IS LOAD-BEARING
--------------------------
`TestHighTierCannotCompleteOnLowerAuth` is the reason this file exists. Every
other test here documents behaviour; that one is the only thing standing between
this pattern and a card being posted to an attacker's address.

It was verified by deletion, not by reading. Removing the two-line guard from
`tools/banking.py::reissue_card`:

    -    try:
    -        require_tier("reissue_card", context)
    -    except StepUpRequired as exc:
    -        return _step_up(exc, context)

turns that class red — `test_medium_auth_cannot_reissue_a_card` and
`test_refusal_carries_no_dispatch_data` both fail, reporting a dispatch
reference returned to a caller holding MEDIUM. The guard was restored
afterwards. That exercise is the difference between a test and a docstring, and
it is worth repeating on any change to the guard.

The tests deliberately call the tools DIRECTLY rather than through a
conversation. A conversation test can only tell you the model chose not to call
the tool this time; calling the tool with insufficient auth and watching it
refuse tells you the model's choice does not matter. Both layers ship —
`tests/e2e/` covers the conversational half — but only this one is a proof.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from authpolicy import (  # noqa: E402
    POLICIES,
    RETRY_BUDGET,
    AuthTier,
    Outcome,
    StepUpRequired,
    check_otp,
    check_passphrase,
    coerce,
    evaluate,
    factor_for,
    grant,
    redact,
    require_tier,
    revoke,
    tier_for,
)


class FakeMemory:
    """The slice of Rasa's memory API the guard touches."""

    def __init__(self, **initial: object) -> None:
        self._data: dict[str, object] = dict(initial)

    def get(self, key: str) -> object:
        return self._data.get(key)

    def set(self, key: str, value: object) -> None:
        self._data[key] = value


class FakeContext:
    """Stand-in for ToolContext. Keeps the suite runnable without an agent."""

    def __init__(self, **initial: object) -> None:
        self.memory = FakeMemory(**initial)


def caller_at(tier: AuthTier | str, **extra: object) -> FakeContext:
    """A context for a caller holding `tier`."""
    value = tier.value if isinstance(tier, AuthTier) else tier
    return FakeContext(auth_tier=value, **extra)


def run(coro):
    """Drive one async tool call to completion."""
    return asyncio.run(coro)


def payload(result) -> dict:
    """The dict a ToolResult carries back to the model."""
    return result.llm_response


# ==============================================================================
# THE LOAD-BEARING TEST
# ==============================================================================


class TestHighTierCannotCompleteOnLowerAuth(unittest.TestCase):
    """A high-tier action must not complete on low or medium auth.

    Delete the guard in tools/banking.py and this class goes red. That has been
    checked by actually doing it — see this module's docstring.
    """

    def test_medium_auth_cannot_reissue_a_card(self):
        """The whole pattern in one assertion.

        MEDIUM is a *correct* passphrase, honestly earned. The caller may well
        be the real customer. It is still not enough to post a card, because the
        tier is a property of the action and reissue_card is HIGH.
        """
        from tools.banking import reissue_card

        context = caller_at(AuthTier.MEDIUM)
        result = payload(
            run(reissue_card(delivery_address="12 Elsewhere Street", context=context))
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["step_up_required"])
        self.assertEqual(result["required_tier"], "high")
        self.assertEqual(result["held_tier"], "medium")
        # The action did not happen. These keys exist only on success.
        self.assertNotIn("dispatched", result)
        self.assertNotIn("reference", result)

    def test_low_auth_cannot_reissue_a_card(self):
        from tools.banking import reissue_card

        result = payload(run(reissue_card(context=caller_at(AuthTier.LOW))))
        self.assertFalse(result["ok"])
        self.assertNotIn("reference", result)

    def test_unauthenticated_caller_cannot_reissue_a_card(self):
        from tools.banking import reissue_card

        result = payload(run(reissue_card(context=caller_at(AuthTier.NONE))))
        self.assertFalse(result["ok"])
        self.assertNotIn("reference", result)

    def test_medium_auth_cannot_transfer_funds(self):
        from tools.banking import transfer_funds

        result = payload(
            run(
                transfer_funds(
                    amount="4000", destination="external", context=caller_at(AuthTier.MEDIUM)
                )
            )
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["required_tier"], "high")
        self.assertNotIn("transferred", result)

    def test_refusal_carries_no_dispatch_data(self):
        """A refusal must disclose nothing. Partial success is still success.

        The tempting failure here is a refusal that helpfully includes the
        address on file, or the last four digits of the card being replaced, so
        the agent can "confirm the details while we verify". That is a
        disclosure to an unverified caller wearing a denial's clothes.
        """
        from tools.banking import reissue_card

        result = payload(run(reissue_card(context=caller_at(AuthTier.MEDIUM))))
        leaky = {"reference", "dispatched", "eta", "delivery_address"}
        self.assertEqual(leaky & set(result), set())

    def test_every_high_tier_tool_refuses_medium(self):
        """Enumerated from the policy table, so a new HIGH action joins this test.

        A new irreversible tool added without a guard fails here without anyone
        remembering to extend the suite — the loop reads POLICIES, not a list
        maintained by hand.
        """
        import tools.banking as banking

        high_actions = [name for name, p in POLICIES.items() if p.tier is AuthTier.HIGH]
        self.assertTrue(high_actions, "no HIGH actions declared — table is wrong")

        for action in high_actions:
            with self.subTest(action=action):
                tool_fn = getattr(banking, action)
                result = payload(run(tool_fn(context=caller_at(AuthTier.MEDIUM))))
                self.assertFalse(
                    result.get("ok"),
                    f"{action} completed on medium auth — it is declared HIGH",
                )


# ==============================================================================
# The rest: behaviour this pattern claims, asserted
# ==============================================================================


class TestTierLattice(unittest.TestCase):
    def test_ordering_is_strict(self):
        self.assertLess(AuthTier.NONE.rank, AuthTier.LOW.rank)
        self.assertLess(AuthTier.LOW.rank, AuthTier.MEDIUM.rank)
        self.assertLess(AuthTier.MEDIUM.rank, AuthTier.HIGH.rank)

    def test_satisfies_is_greater_or_equal_not_equal(self):
        """A caller at HIGH is not re-challenged for a MEDIUM action."""
        self.assertTrue(AuthTier.HIGH.satisfies(AuthTier.MEDIUM))
        self.assertTrue(AuthTier.HIGH.satisfies(AuthTier.HIGH))
        self.assertFalse(AuthTier.MEDIUM.satisfies(AuthTier.HIGH))

    def test_full_decision_matrix(self):
        """All 4x3 combinations, written out rather than computed.

        Computing the expectation with the same `>=` the guard uses would make
        this test pass for any consistent implementation, including a wrong one.
        """
        expected = {
            (AuthTier.NONE, AuthTier.LOW): False,
            (AuthTier.NONE, AuthTier.MEDIUM): False,
            (AuthTier.NONE, AuthTier.HIGH): False,
            (AuthTier.LOW, AuthTier.LOW): True,
            (AuthTier.LOW, AuthTier.MEDIUM): False,
            (AuthTier.LOW, AuthTier.HIGH): False,
            (AuthTier.MEDIUM, AuthTier.LOW): True,
            (AuthTier.MEDIUM, AuthTier.MEDIUM): True,
            (AuthTier.MEDIUM, AuthTier.HIGH): False,
            (AuthTier.HIGH, AuthTier.LOW): True,
            (AuthTier.HIGH, AuthTier.MEDIUM): True,
            (AuthTier.HIGH, AuthTier.HIGH): True,
        }
        for (held, required), want in expected.items():
            with self.subTest(held=held.value, required=required.value):
                self.assertEqual(held.satisfies(required), want)

    def test_coerce_fails_closed(self):
        """Anything unrecognised is unauthenticated."""
        for junk in (None, "", "  ", "administrator", "HIGH ", 3, ["high"], object()):
            with self.subTest(junk=repr(junk)):
                if junk == "HIGH ":
                    self.assertEqual(coerce(junk), AuthTier.HIGH)  # whitespace/case ok
                else:
                    self.assertEqual(coerce(junk), AuthTier.NONE)

    def test_coerce_does_not_raise(self):
        """A guard that throws gets wrapped in a bare except within a month."""
        try:
            coerce(object())
        except Exception as exc:  # pragma: no cover
            self.fail(f"coerce raised {exc!r}")


class TestActionTable(unittest.TestCase):
    def test_tier_is_declared_per_action(self):
        self.assertEqual(tier_for("get_store_hours"), AuthTier.LOW)
        self.assertEqual(tier_for("get_balance"), AuthTier.MEDIUM)
        self.assertEqual(tier_for("reissue_card"), AuthTier.HIGH)

    def test_unknown_action_defaults_to_high(self):
        """Forgetting to classify a new action must not open a hole."""
        self.assertEqual(tier_for("close_account"), AuthTier.HIGH)
        self.assertEqual(tier_for(""), AuthTier.HIGH)

    def test_every_irreversible_action_is_high(self):
        """The table cannot declare something irreversible and cheap to reach."""
        for name, policy in POLICIES.items():
            if policy.irreversible:
                with self.subTest(action=name):
                    self.assertIs(policy.tier, AuthTier.HIGH)

    def test_every_policy_states_a_reason(self):
        for name, policy in POLICIES.items():
            with self.subTest(action=name):
                self.assertTrue(policy.reason.strip(), f"{name} has no reason")


class TestGuardResolution(unittest.TestCase):
    def test_missing_context_is_unauthenticated(self):
        """Tool-discovery probes and unit tests must not act as a bypass."""
        with self.assertRaises(StepUpRequired):
            require_tier("reissue_card", None)

    def test_raises_rather_than_returning_falsy(self):
        """A return value can be ignored; an exception cannot."""
        with self.assertRaises(StepUpRequired) as caught:
            require_tier("transfer_funds", caller_at(AuthTier.MEDIUM))
        self.assertEqual(caught.exception.required, AuthTier.HIGH)
        self.assertEqual(caught.exception.held, AuthTier.MEDIUM)

    def test_allows_when_tier_is_sufficient(self):
        decision = require_tier("get_balance", caller_at(AuthTier.MEDIUM))
        self.assertTrue(decision.allowed)

    def test_evaluate_is_pure(self):
        """Same inputs, same Decision, no side effects to sequence around."""
        first = evaluate("reissue_card", "medium")
        second = evaluate("reissue_card", "medium")
        self.assertEqual(first, second)
        self.assertFalse(first.allowed)


class TestStepUpIsRequiredNotRemembered(unittest.TestCase):
    """The charter's sharpest requirement: medium-then-high must step up."""

    def test_medium_caller_attempting_high_is_stepped_up(self):
        from tools.banking import get_balance, reissue_card

        context = caller_at(AuthTier.MEDIUM)

        # The medium action succeeds.
        self.assertTrue(payload(run(get_balance(context=context)))["ok"])

        # The high action, same caller, same call, is refused.
        refusal = payload(run(reissue_card(context=context)))
        self.assertFalse(refusal["ok"])
        self.assertEqual(refusal["factor"], "otp")

        # And the refusal recorded what to resume, so the conversation can recover.
        self.assertEqual(context.memory.get("pending_action"), "reissue_card")
        self.assertEqual(context.memory.get("pending_tier"), "high")

    def test_high_caller_is_not_rechallenged_for_medium(self):
        """Step-up must not become step-up-every-time, or teams disable it."""
        from tools.banking import get_balance

        self.assertTrue(payload(run(get_balance(context=caller_at(AuthTier.HIGH))))["ok"])

    def test_grant_is_monotonic(self):
        """A later low-tier interaction cannot weaken a caller."""
        context = caller_at(AuthTier.HIGH)
        held = grant(context, AuthTier.MEDIUM, "passphrase")
        self.assertEqual(held, AuthTier.HIGH)
        self.assertEqual(context.memory.get("auth_tier"), "high")

    def test_grant_raises_a_lower_caller(self):
        context = caller_at(AuthTier.NONE)
        self.assertEqual(grant(context, AuthTier.MEDIUM, "passphrase"), AuthTier.MEDIUM)

    def test_low_tier_tools_never_challenge(self):
        """Public information for an anonymous caller, with no ceremony."""
        from tools.banking import get_fee_schedule, get_store_hours

        for tool_fn in (get_store_hours, get_fee_schedule):
            with self.subTest(tool=tool_fn.__name__):
                result = payload(run(tool_fn(context=caller_at(AuthTier.NONE))))
                self.assertTrue(result["ok"])


class TestFailurePaths(unittest.TestCase):
    """Retry budget, lockout, and the downgrade that must never happen."""

    def test_wrong_passphrase_retries_then_locks_out(self):
        first = check_passphrase("wrong", attempts_used=0)
        self.assertIs(first.outcome, Outcome.RETRY)
        self.assertEqual(first.attempts_remaining, RETRY_BUDGET - 1)

        final = check_passphrase("wrong again", attempts_used=first.attempts_used)
        self.assertIs(final.outcome, Outcome.LOCKED_OUT)
        self.assertTrue(final.handoff)

    def test_a_failed_challenge_never_grants_a_tier(self):
        """There is no code path from failure to authenticated."""
        for used in range(RETRY_BUDGET + 2):
            for check in (check_passphrase, check_otp):
                with self.subTest(check=check.__name__, used=used):
                    result = check("definitely not the secret", attempts_used=used)
                    self.assertIsNot(result.outcome, Outcome.PASSED)
                    self.assertIsNone(result.granted)

    def test_lockout_requires_handoff(self):
        result = check_otp("nope", attempts_used=RETRY_BUDGET)
        self.assertIs(result.outcome, Outcome.LOCKED_OUT)
        self.assertTrue(result.handoff)
        self.assertIsNone(result.granted)

    def test_passphrase_ceiling_is_medium(self):
        """A knowledge factor cannot reach HIGH however correct it is."""
        result = check_passphrase("blue harbor", attempts_used=0)
        self.assertIs(result.outcome, Outcome.PASSED)
        self.assertIs(result.granted, AuthTier.MEDIUM)
        self.assertFalse(result.granted.satisfies(AuthTier.HIGH))

    def test_otp_grants_high(self):
        result = check_otp("one nine three seven", attempts_used=0)
        self.assertIs(result.outcome, Outcome.PASSED)
        self.assertIs(result.granted, AuthTier.HIGH)

    def test_spoken_factor_normalizes_casing_and_punctuation(self):
        """ASR variation must not become a false rejection the caller can't fix."""
        for spoken in ("Blue Harbor", "  blue   harbor ", "Blue harbor.", "blue, harbor"):
            with self.subTest(spoken=spoken):
                self.assertIs(check_passphrase(spoken, 0).outcome, Outcome.PASSED)

    def test_lockout_revokes_the_tier(self):
        """After lockout the caller holds nothing, so nothing can be spent."""
        context = caller_at(AuthTier.MEDIUM)
        revoke(context)
        self.assertEqual(context.memory.get("auth_tier"), "none")
        with self.assertRaises(StepUpRequired):
            require_tier("get_balance", context)

    def test_locked_out_caller_cannot_complete_the_high_action(self):
        """The downgrade bug, asserted directly.

        Fail the OTP out of budget, then attempt the action anyway. The tool
        must still refuse — the failure path and the guard are independent, and
        this asserts the second one alone.
        """
        from tools.banking import reissue_card

        context = caller_at(AuthTier.MEDIUM, otp_attempts=float(RETRY_BUDGET))
        revoke(context)
        result = payload(run(reissue_card(context=context)))
        self.assertFalse(result["ok"])
        self.assertNotIn("reference", result)


class TestFactorRouting(unittest.TestCase):
    def test_factor_matches_required_tier(self):
        self.assertEqual(factor_for(AuthTier.HIGH), "otp")
        self.assertEqual(factor_for(AuthTier.MEDIUM), "passphrase")
        self.assertEqual(factor_for(AuthTier.LOW), "none")


class TestSecretHandling(unittest.TestCase):
    """A voice channel makes leaking a factor easy. These assert it does not."""

    def test_redact_never_returns_the_secret(self):
        self.assertNotIn("blue harbor", redact("blue harbor"))
        self.assertNotIn("1937", redact("1937"))

    def test_redact_handles_empty_input(self):
        self.assertEqual(redact(""), "<empty>")

    def test_refusal_payload_contains_no_factor_value(self):
        """The refusal is shown to the model; the secret must not ride along."""
        from authpolicy.challenges import DEMO_OTP, DEMO_PASSPHRASE
        from tools.banking import reissue_card

        result = payload(run(reissue_card(context=caller_at(AuthTier.MEDIUM))))
        blob = repr(result).lower()
        self.assertNotIn(DEMO_PASSPHRASE.lower(), blob)
        self.assertNotIn(DEMO_OTP.lower(), blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)
