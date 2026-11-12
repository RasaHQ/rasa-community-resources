"""The manual trial path, with a fake transport: no network, no secret, no quota used."""
import base64
import json
from pathlib import Path
import tempfile
import unittest

import httpx

from premier_demo import trial
from premier_demo.quota import Ledger, QuotaRefused
from tests.support import load_contract

KEY, SECRET = "key-value", "secret-value"
ENV = {"FISERV_BH_API_KEY_NAME": "NAME", "FISERV_BH_API_KEY": KEY, "FISERV_BH_API_SECRET": SECRET}
BINDING = ("trial-1", "2026-11", "999990301", "runner-1")


class Wall:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.wall = Wall()
        self.ledger = Ledger(Path(self.folder.name) / "q.sqlite3", clock=self.wall)
        self.addCleanup(self.ledger.close)
        record = {"budget_id": "B1", "trial_id": "trial-1", "period_id": "2026-11",
                  "organization_id": "999990301", "runner_id": "runner-1", "operator": "op",
                  "as_of": self.wall.now, "expires_at": self.wall.now + 300,
                  "remaining_core_attempts": 5, "basis": "test allocation"}
        self.ledger.import_budget(json.dumps(record).encode(), approved_runner="runner-1")
        self.calls = []

    def handler(self, request):
        self.calls.append(request)
        if request.url == httpx.URL(trial.TOKEN_URL):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 899000, "token_type": "Bearer"})
        return httpx.Response(200, json={"Status": {"StatusCode": "1120", "Severity": "Info",
                                                    "StatusDesc": "No Records Match Selection Criteria",
                                                    "SvcProviderName": "Premier"}})

    def test_missing_or_partial_secrets_stay_mock_and_name_nothing(self):
        for env in ({}, {"FISERV_BH_API_KEY": KEY}, dict(ENV, FISERV_BH_API_SECRET=" ")):
            with self.assertRaises(trial.TrialUnavailable) as raised:
                trial.credentials(env)
            self.assertNotIn("FISERV", str(raised.exception))
            self.assertNotIn(KEY, str(raised.exception))

    def test_token_uses_basic_auth_once_per_run(self):
        transport = httpx.MockTransport(self.handler)
        self.assertEqual(trial.fetch_token(KEY, SECRET, self.ledger, "run", transport=transport), "tok")
        sent = self.calls[0]
        self.assertEqual(sent.headers["Authorization"],
                         "Basic " + base64.b64encode(f"{KEY}:{SECRET}".encode()).decode())
        self.assertEqual(sent.content, b"grant_type=client_credentials")
        with self.assertRaises(QuotaRefused):
            trial.fetch_token(KEY, SECRET, self.ledger, "run", transport=transport)
        self.assertEqual(len(self.calls), 1)

    def test_core_call_is_charged_before_sending_and_carries_bearer_and_efx_header(self):
        contract = load_contract()
        reservation = self.ledger.reserve("run", BINDING, 1)
        client = trial.TrialClient(contract, "tok", self.ledger, reservation,
                                   transport=httpx.MockTransport(self.handler))
        self.assertEqual(client.party_accounts("1"), [])  # observed trial "no records" shape
        sent = self.calls[0]
        self.assertTrue(str(sent.url).startswith(trial.CORE_BASE))
        self.assertEqual(sent.headers["Authorization"], "Bearer tok")
        self.assertEqual(json.loads(sent.headers["EFXHeader"])["OrganizationId"], "999990301")
        self.assertEqual(self.ledger.snapshot(BINDING), {"remaining": 4, "held": 0, "blocked": False})
        self.wall.now += 7
        with self.assertRaises(trial.Unavailable):  # the reservation is spent: nothing is sent
            client.party_accounts("1")
        self.assertEqual(len(self.calls), 1)

    def test_two_reads_in_one_run_wait_for_spacing_then_unused_holds_are_released(self):
        contract = load_contract()
        reservation = self.ledger.reserve("run", BINDING, 3)
        slept = []

        def fake_sleep(seconds):
            slept.append(seconds)
            self.wall.now += seconds

        client = trial.TrialClient(contract, "tok", self.ledger, reservation,
                                   transport=httpx.MockTransport(self.handler), sleep=fake_sleep)
        client.party_accounts("1")
        client.party_accounts("2")  # waits for the 7 s spacing instead of failing
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(slept, [7.0])
        self.assertEqual(self.ledger.snapshot(BINDING), {"remaining": 3, "held": 1, "blocked": False})
        self.assertEqual(self.ledger.release_unused(reservation, "end of run"), 1)
        self.assertEqual(self.ledger.snapshot(BINDING), {"remaining": 3, "held": 0, "blocked": False})
        with self.assertRaises(QuotaRefused):
            self.ledger.release_unused(reservation, " ")
        self.assertEqual(self.ledger.release_unused(reservation, "again"), 0)  # nothing left; nothing replenished

    def test_the_trial_client_never_moves_money(self):
        client = trial.TrialClient(load_contract(), "tok", self.ledger, 0,
                                   transport=httpx.MockTransport(self.handler))
        with self.assertRaises(trial.TrialUnavailable):
            client.transfer("a", "b", 1)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
