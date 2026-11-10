#!/usr/bin/env python3
"""SIM swap: the number cannot vouch for itself. No network, model or keys.

    make test

The tests call the policy in `lib/sim_swap.py` and the tools in
`skills/sim_swap/tools.py` directly, with a fake context and a throwaway
SQLite file. A conversation test can only show that the model chose not to
call `request_sim_swap` on one sampled run. Calling the tool with a circular or
knowledge-only verification and watching it refuse shows the model's choice
does not matter.

VERIFIED BY DELETION
--------------------
Each check below was deleted, the suite run, and the file restored and
compared byte for byte with a copy taken first. All runs 2026-09-21, eleven
tests. The counts are unittest failures, where each failing subtest counts
once.

1. The guard at the top of `skills/sim_swap/tools.py::request_sim_swap`:

       -    try:
       -        require_independent_verification(line, context)
       -    except SwapRefused as exc:
       -        return _refuse(exc, context)

   The suite went red: 8 of the 11 tests failed, 32 failures in all
   (test_sms_code_to_the_line_being_replaced_is_refused,
   test_knowledge_factors_never_authorise_a_swap,
   test_changing_the_target_line_discards_the_verification,
   test_device_registered_during_the_call_does_not_count,
   test_refusal_returns_no_swap_reference,
   test_widening_the_channel_set_does_not_open_a_new_path,
   test_resending_a_push_does_not_reset_the_attempt_budget and
   test_malformed_verification_fails_closed). Each one was a swap reference
   returned, or a queued row written, for a caller who had not verified
   independently. Three tests stayed green, because they describe a caller the
   guard should let through or never reach request_sim_swap:
   test_app_push_to_a_registered_device_authorises_the_swap,
   test_a_queued_request_is_not_reported_as_active and
   test_unverified_caller_learns_nothing_about_the_device.

2. The target binding in `lib/sim_swap.py::evaluate_swap`:

       -    if line_digits(record.issued_for_line) != line_digits(target):
       -        return refuse(TARGET_CHANGED)

   3 failures in 2 tests, and each direction was seen once.
   test_changing_the_target_line_discards_the_verification failed on its
   first, policy-level assertion. `evaluate_swap` returned `allowed` for a push
   issued for 555-0142 when 555-0187 was requested. In
   test_refusal_returns_no_swap_reference the tool itself queued a swap of
   555-0142 on a push issued for 555-0187. That test failed twice: once in
   its "other line" case, where ok came back True, and once on its check that
   no row was written. This check stops a swap. It is not only a label.

3. The knowledge check in evaluate_swap: 3 failures, all in
   test_knowledge_factors_never_authorise_a_swap.
4. The circular check in evaluate_swap: 2 failures, all in
   test_sms_code_to_the_line_being_replaced_is_refused.

   For 3 and 4 the swap was STILL refused, as `no_verification`, because the
   policy accepts only the two independent channels. The tests caught the
   wrong reason code, not a swap. Those two checks make the refusal explain
   itself. The allowlist and the guard are what stop the swap.

5. The call-start comparison in `_trusted_push_device` (keeping only
   `registered is not None`): 1 failure, in
   test_device_registered_during_the_call_does_not_count. The push went to
   DEV-125-01, a device registered four minutes after the call began.

6. The explicit channel gate in send_swap_verification, reverted to the
   earlier `if wanted not in INDEPENDENT_CHANNELS:`. That gate sent every
   accepted channel other than store_id_check down the push path. 1 failure,
   in test_widening_the_channel_set_does_not_open_a_new_path: with "email"
   patched into INDEPENDENT_CHANNELS, send returned ok True for "email".

7. The deliberate absence of an attempt reset in `_discard_verification`
   (adding `context.memory.set(ATTEMPTS_KEY, 0.0)` there): 1 failure, in
   test_resending_a_push_does_not_reset_the_attempt_budget. After one wrong
   code and a re-sent push, the second wrong code came back `retry`, not
   `locked_out`. The re-send had handed out a fresh budget.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.sim_swap import (  # noqa: E402
    ALLOWED,
    CIRCULAR_VERIFICATION,
    KNOWLEDGE_ONLY,
    NO_VERIFICATION,
    TARGET_CHANGED,
    SwapVerification,
    evaluate_swap,
)


def _load_tools():
    """Import skills/sim_swap/tools.py the way the engine finds it: by path."""
    path = PROJECT_ROOT / "skills" / "sim_swap" / "tools.py"
    spec = importlib.util.spec_from_file_location("sim_swap_tools", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tools = _load_tools()

LINE = "555-0142"
OTHER_LINE = "555-0187"
NEW_ICCID = "8901410427163557201"
# The call these tests simulate starts here. DEV-123-01 was registered in 2025,
# before it; DEV-125-01 was registered at 10:04 the same day, during it.
CALL_START = "2026-09-21T10:00:00Z"
DEVICE_DETAILS = ("DEV-123-01", "DEV-123-02", "DEV-125-01", "tablet", "phone", "Telecom of Rasa app on")
SUCCESS_ONLY_KEYS = {"reference", "status", "active", "receipt_proves"}


class FakeMemory:
    """The slice of Rasa's memory API the tools touch."""

    def __init__(self, **initial: object) -> None:
        self._data: dict[str, object] = dict(initial)

    def get(self, key: str, default: object = None) -> object:
        value = self._data.get(key)
        return default if value is None else value

    def set(self, key: str, value: object) -> None:
        self._data[key] = value

    def snapshot(self) -> dict[str, object]:
        return dict(self._data)


class FakeContext:
    """Stand-in for ToolContext: memory only, which is all these tools use."""

    def __init__(self, **initial: object) -> None:
        initial.setdefault("customer_id", "123")
        initial.setdefault("swap_call_started_at", CALL_START)
        self.memory = FakeMemory(**initial)


def run(coro):
    return asyncio.run(coro)


def payload(result) -> dict:
    return result.llm_response


def record(channel: str, *, destination: str = LINE, issued_for: str = LINE,
           passed: bool = True, registered: bool = False) -> SwapVerification:
    return SwapVerification(
        channel=channel,
        destination=destination,
        issued_for_line=issued_for,
        passed=passed,
        registered_before_call=registered,
    )


def caller_holding(verification: SwapVerification | object) -> FakeContext:
    """A caller whose memory holds `verification` exactly as memory would."""
    value = verification.to_json() if isinstance(verification, SwapVerification) else verification
    return FakeContext(swap_verification=value)


class SimSwapTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "telco.db"
        tools.DATABASE_PATH = self.db_path

    def tearDown(self) -> None:
        tools.DATABASE_PATH = None
        self._tmp.cleanup()

    # -- helpers -----------------------------------------------------------

    def swap_rows(self) -> list[tuple]:
        tools._database().connection.close()  # make sure the file is seeded
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT reference, line, status FROM sim_swaps ORDER BY id"
            ).fetchall()

    def verify_by_app_push(self, context: FakeContext, line: str = LINE) -> None:
        sent = payload(run(tools.send_swap_verification(line=line, channel="app_push", context=context)))
        self.assertTrue(sent["ok"], sent)
        confirmed = payload(run(tools.confirm_swap_verification(code=tools.DEMO_PUSH_CODE, context=context)))
        self.assertTrue(confirmed["ok"], confirmed)

    def assert_refused_without_reference(self, result: dict, reason: str | None = None) -> None:
        self.assertIs(result["ok"], False)
        self.assertEqual(SUCCESS_ONLY_KEYS & set(result), set(), result)
        if reason is not None:
            self.assertEqual(result["reason"], reason)

    # -- the cited tests ---------------------------------------------------

    def test_sms_code_to_the_line_being_replaced_is_refused(self):
        """A code to the target line is circular, even when read back correctly."""
        for channel in ("sms", "voice_call"):
            with self.subTest(channel=channel):
                decision = evaluate_swap(LINE, record(channel, passed=True))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, CIRCULAR_VERIFICATION)

                # Digits are compared, not formatting.
                decision = evaluate_swap("5550142", record(channel, destination="555 0142", issued_for="555.0142"))
                self.assertEqual(decision.reason, CIRCULAR_VERIFICATION)

                # The tool will not even send one.
                sent = payload(run(tools.send_swap_verification(line=LINE, channel=channel, context=FakeContext())))
                self.assertIs(sent["ok"], False)
                self.assertEqual(sent["reason"], CIRCULAR_VERIFICATION)

                # And a passed SMS record already in memory cannot be spent.
                before = self.swap_rows()
                result = payload(run(tools.request_sim_swap(
                    line=LINE, new_iccid=NEW_ICCID, context=caller_holding(record(channel)))))
                self.assert_refused_without_reference(result, CIRCULAR_VERIFICATION)
                self.assertEqual(self.swap_rows(), before)

    def test_knowledge_factors_never_authorise_a_swap(self):
        """PIN, date of birth and security answers: refused however correct."""
        for channel in ("pin", "dob", "security_answer"):
            with self.subTest(channel=channel):
                decision = evaluate_swap(LINE, record(channel, destination="caller", passed=True))
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, KNOWLEDGE_ONLY)

                sent = payload(run(tools.send_swap_verification(line=LINE, channel=channel, context=FakeContext())))
                self.assertIs(sent["ok"], False)
                self.assertEqual(sent["reason"], KNOWLEDGE_ONLY)

                before = self.swap_rows()
                result = payload(run(tools.request_sim_swap(
                    line=LINE, new_iccid=NEW_ICCID,
                    context=caller_holding(record(channel, destination="caller")))))
                self.assert_refused_without_reference(result, KNOWLEDGE_ONLY)
                self.assertEqual(self.swap_rows(), before)

    def test_app_push_to_a_registered_device_authorises_the_swap(self):
        """The one remote path that works, end to end, with the code kept out."""
        self.assertEqual(
            evaluate_swap(LINE, record("app_push", destination="registered_device", registered=True)).reason,
            ALLOWED,
        )
        self.assertEqual(
            evaluate_swap(LINE, record("store_id_check", destination="store")).reason,
            ALLOWED,
        )
        # A device enrolled during the call is not independent of the caller.
        self.assertEqual(
            evaluate_swap(LINE, record("app_push", destination="registered_device", registered=False)).reason,
            NO_VERIFICATION,
        )

        context = FakeContext()
        sent = payload(run(tools.send_swap_verification(line=LINE, channel="app_push", context=context)))
        self.assertTrue(sent["ok"])
        stored = json.loads(context.memory.get("swap_verification"))
        self.assertEqual(stored["destination"], "registered_device")
        self.assertIs(stored["registered_before_call"], True)  # DEV-123-01, from 2025
        self.assertIs(stored["passed"], False)

        # Spoken the way ASR hands it over; normalised before comparison.
        with self.assertLogs(tools.logger, level="INFO") as logs:
            confirmed = payload(run(tools.confirm_swap_verification(
                code="Six two, eight four.", context=context)))
        self.assertTrue(confirmed["ok"])

        result = payload(run(tools.request_sim_swap(line=LINE, new_iccid=NEW_ICCID, context=context)))
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["reference"].startswith("SWP-"))
        self.assertEqual(result["status"], "queued")
        self.assertIn((result["reference"], LINE, "queued"), self.swap_rows())

        # The verification is single use.
        self.assertIsNone(context.memory.get("swap_verification"))

        # The code never reaches a tool result, memory, or a log line.
        blob = " ".join([repr(sent), repr(confirmed), repr(result),
                         repr(context.memory.snapshot()), " ".join(logs.output)]).lower()
        self.assertNotIn(tools.DEMO_PUSH_CODE, blob)
        self.assertNotIn("six two, eight four", blob)
        self.assertNotIn(NEW_ICCID, blob)

    def test_changing_the_target_line_discards_the_verification(self):
        """Verified line A, asked to move line B: refused, and A's proof is gone."""
        decision = evaluate_swap(OTHER_LINE, record("app_push", destination="registered_device", registered=True))
        self.assertEqual(decision.reason, TARGET_CHANGED)

        context = FakeContext()
        self.verify_by_app_push(context, LINE)

        switched = payload(run(tools.request_sim_swap(line=OTHER_LINE, new_iccid=NEW_ICCID, context=context)))
        self.assert_refused_without_reference(switched, TARGET_CHANGED)
        self.assertIsNone(context.memory.get("swap_verification"))

        # Switching back does not resurrect it.
        back = payload(run(tools.request_sim_swap(line=LINE, new_iccid=NEW_ICCID, context=context)))
        self.assert_refused_without_reference(back, NO_VERIFICATION)
        self.assertEqual([r for r in self.swap_rows() if r[2] == "queued"], [])

    def test_refusal_returns_no_swap_reference(self):
        """Every refusal: ok False, no reference, and nothing written."""
        pending_push = record("app_push", destination="registered_device", registered=True, passed=False)
        cases = {
            "no context": None,
            "empty memory": FakeContext(),
            "knowledge": caller_holding(record("pin", destination="caller")),
            "circular": caller_holding(record("sms")),
            "other line": caller_holding(record("app_push", destination="registered_device",
                                                issued_for=OTHER_LINE, registered=True)),
            "push not yet confirmed": caller_holding(pending_push),
            "locked out": FakeContext(
                swap_verification=record("app_push", destination="registered_device", registered=True).to_json(),
                swap_locked_out=True,
            ),
        }
        before = self.swap_rows()
        for label, context in cases.items():
            with self.subTest(case=label):
                result = payload(run(tools.request_sim_swap(line=LINE, new_iccid=NEW_ICCID, context=context)))
                self.assert_refused_without_reference(result)
                self.assertTrue(result["refused"])
        self.assertEqual(self.swap_rows(), before)

        # Exhausting the code budget locks the call and leaves nothing to spend.
        context = FakeContext()
        run(tools.send_swap_verification(line=LINE, channel="app_push", context=context))
        for _ in range(tools.RETRY_BUDGET):
            last = payload(run(tools.confirm_swap_verification(code="one one one one", context=context)))
        self.assertEqual(last["outcome"], "locked_out")
        self.assertTrue(last["handoff_required"])
        late = payload(run(tools.confirm_swap_verification(code=tools.DEMO_PUSH_CODE, context=context)))
        self.assertIs(late["ok"], False)
        result = payload(run(tools.request_sim_swap(line=LINE, new_iccid=NEW_ICCID, context=context)))
        self.assert_refused_without_reference(result, NO_VERIFICATION)

    def test_a_queued_request_is_not_reported_as_active(self):
        """The receipt proves a request, not a working SIM."""
        context = FakeContext()
        self.verify_by_app_push(context)
        queued = payload(run(tools.request_sim_swap(line=LINE, new_iccid=NEW_ICCID, context=context)))
        self.assertEqual(queued["status"], "queued")
        self.assertIs(queued["active"], False)

        status = payload(run(tools.check_swap_status(reference=queued["reference"], context=context)))
        self.assertTrue(status["ok"])
        self.assertEqual(status["status"], "queued")
        self.assertIs(status["active"], False)

        # The status is read from the store, not assumed: a finished swap in
        # the fixtures reports active.
        finished = payload(run(tools.check_swap_status(reference="SWP-1001", context=context)))
        self.assertEqual(finished["status"], "active")
        self.assertIs(finished["active"], True)

        unknown = payload(run(tools.check_swap_status(reference="SWP-0000", context=context)))
        self.assertIs(unknown["ok"], False)
        self.assertNotIn("status", unknown)

    def test_unverified_caller_learns_nothing_about_the_device(self):
        """Before verification, the push destination is described, never named."""
        context = FakeContext()
        sent = payload(run(tools.send_swap_verification(line=LINE, channel="app_push", context=context)))
        self.assertTrue(sent["ok"])
        self.assertEqual(sent["destination"], tools.NEUTRAL_DEVICE_PHRASE)
        blob = (repr(sent) + repr(context.memory.snapshot())).lower()
        for detail in DEVICE_DETAILS:
            with self.subTest(detail=detail):
                self.assertNotIn(detail.lower(), blob)

    def test_device_registered_during_the_call_does_not_count(self):
        """A device enrolled after the call began was enrolled on the caller's word."""
        # Policy: a push to a device not registered before the call is no verification.
        decision = evaluate_swap("555-0175", record(
            "app_push", destination="registered_device", issued_for="555-0175", registered=False))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, NO_VERIFICATION)

        # Tools: customer 125's only device was registered at 10:04, the call began at 10:00.
        context = FakeContext(customer_id="125")
        sent = payload(run(tools.send_swap_verification(line="555-0175", channel="app_push", context=context)))
        self.assertIs(sent["ok"], False)
        self.assertEqual(sent["reason"], "no_independent_path")
        self.assertTrue(sent["handoff_required"])
        self.assertIsNone(context.memory.get("swap_verification"))
        self.assertNotIn("dev-125-01", repr(sent).lower())

        result = payload(run(tools.request_sim_swap(line="555-0175", new_iccid=NEW_ICCID, context=context)))
        self.assert_refused_without_reference(result, NO_VERIFICATION)

        # The same device counts when the call began after it was registered,
        # which shows the comparison is on the timestamps and not a fixed list.
        later = FakeContext(customer_id="125", swap_call_started_at="2026-09-21T10:30:00Z")
        self.assertTrue(payload(run(tools.send_swap_verification(
            line="555-0175", channel="app_push", context=later)))["ok"])

        # With no call start in memory, one is fixed on first use and kept.
        fresh = FakeContext(swap_call_started_at=None)
        run(tools.send_swap_verification(line=LINE, channel="app_push", context=fresh))
        first = fresh.memory.get("swap_call_started_at")
        self.assertIsNotNone(first)
        run(tools.send_swap_verification(line=LINE, channel="app_push", context=fresh))
        self.assertEqual(fresh.memory.get("swap_call_started_at"), first)

    def test_widening_the_channel_set_does_not_open_a_new_path(self):
        """Adding a name to INDEPENDENT_CHANNELS must not create an approval path."""
        import lib.sim_swap as policy

        widened = policy.INDEPENDENT_CHANNELS | {"email"}
        with mock.patch.object(policy, "INDEPENDENT_CHANNELS", widened), \
                mock.patch.object(tools, "INDEPENDENT_CHANNELS", widened):
            context = FakeContext()
            sent = payload(run(tools.send_swap_verification(line=LINE, channel="email", context=context)))
            self.assertIs(sent["ok"], False)
            self.assertEqual(sent["reason"], NO_VERIFICATION)
            self.assertIsNone(context.memory.get("swap_verification"))  # nothing written

            # Even a code read back cannot pass: there is no pending record.
            confirmed = payload(run(tools.confirm_swap_verification(
                code=tools.DEMO_PUSH_CODE, context=context)))
            self.assertIs(confirmed["ok"], False)

            before = self.swap_rows()
            result = payload(run(tools.request_sim_swap(line=LINE, new_iccid=NEW_ICCID, context=context)))
            self.assert_refused_without_reference(result, NO_VERIFICATION)

            # A passed "email" record placed straight into memory is refused too.
            forged = {"channel": "email", "destination": "caller@example.com",
                      "issued_for_line": LINE, "passed": True, "registered_before_call": True}
            self.assertFalse(evaluate_swap(LINE, forged).allowed)
            result = payload(run(tools.request_sim_swap(
                line=LINE, new_iccid=NEW_ICCID, context=caller_holding(json.dumps(forged)))))
            self.assert_refused_without_reference(result, NO_VERIFICATION)
            self.assertEqual(self.swap_rows(), before)

    def test_resending_a_push_does_not_reset_the_attempt_budget(self):
        """One wrong code, a fresh push, one wrong code: locked out, not a new budget."""
        self.assertEqual(tools.RETRY_BUDGET, 2)  # the arithmetic below assumes it
        context = FakeContext()
        run(tools.send_swap_verification(line=LINE, channel="app_push", context=context))
        first = payload(run(tools.confirm_swap_verification(code="one one one one", context=context)))
        self.assertEqual(first["outcome"], "retry")

        resent = payload(run(tools.send_swap_verification(line=LINE, channel="app_push", context=context)))
        self.assertTrue(resent["ok"])

        second = payload(run(tools.confirm_swap_verification(code="two two two two", context=context)))
        self.assertEqual(second["outcome"], "locked_out")
        self.assertTrue(second["handoff_required"])

        # Locked means locked: no new push, no correct code, no swap.
        again = payload(run(tools.send_swap_verification(line=LINE, channel="app_push", context=context)))
        self.assertEqual(again["outcome"], "locked_out")
        late = payload(run(tools.confirm_swap_verification(code=tools.DEMO_PUSH_CODE, context=context)))
        self.assertIs(late["ok"], False)
        result = payload(run(tools.request_sim_swap(line=LINE, new_iccid=NEW_ICCID, context=context)))
        self.assert_refused_without_reference(result, NO_VERIFICATION)

    def test_malformed_verification_fails_closed(self):
        """Anything that is not a clean, known, passed record is no verification."""
        good = json.loads(record("app_push", destination="registered_device", registered=True).to_json())
        self.assertTrue(evaluate_swap(LINE, good).allowed)  # control: the base record passes

        def mutated(**changes):
            value = dict(good)
            for key, new in changes.items():
                if new is KeyError:
                    value.pop(key)
                else:
                    value[key] = new
            return value

        junk = {
            "None": None,
            "empty string": "",
            "not json": "passed",
            "json list": "[1, 2]",
            "empty object": {},
            "passed as string": mutated(passed="true"),
            "passed as int": mutated(passed=1),
            "registered as string": mutated(registered_before_call="true"),
            "missing passed": mutated(passed=KeyError),
            "missing channel": mutated(channel=KeyError),
            "missing destination": mutated(destination=KeyError),
            "missing issued_for_line": mutated(issued_for_line=KeyError),
            "unknown channel": mutated(channel="email"),
            "channel wrong case": mutated(channel="APP_PUSH"),
            "blank line": mutated(issued_for_line="   "),
            "a list": [good],
            "an object": object(),
        }
        for label, value in junk.items():
            with self.subTest(verification=label):
                decision = evaluate_swap(LINE, value)
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, NO_VERIFICATION)

                if isinstance(value, (dict, str)) or value is None:
                    stored = json.dumps(value) if isinstance(value, dict) else value
                    result = payload(run(tools.request_sim_swap(
                        line=LINE, new_iccid=NEW_ICCID, context=caller_holding(stored))))
                    self.assert_refused_without_reference(result, NO_VERIFICATION)

        for target in (None, "", "no digits", 5550142):
            with self.subTest(target=repr(target)):
                decision = evaluate_swap(target, good)
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, NO_VERIFICATION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
