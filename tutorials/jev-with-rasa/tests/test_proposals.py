"""Proposal lifecycle controls using the real SDK and scripted responses."""
import unittest
from typesafe_sdk import RetryPolicy, TypeSafeClient
from jacaranda_jev.accounts import Accounts
from jacaranda_jev.proposals import Proposals
from jacaranda_jev.scripted import scripted_transport
from jacaranda_jev.selector import MODEL, Selector


class ProposalControls(unittest.TestCase):
    def setUp(self):
        self.accounts = Accounts()
        transport, self.calls = scripted_transport()
        self.client = TypeSafeClient(api_key="scripted-local-test", base_url="https://scripted.invalid",
                                    transport=transport, model=MODEL, retry=RetryPolicy(max_retries=0))
        self.service = Proposals(Selector(self.client, self.accounts))

    def tearDown(self):
        self.client.close()

    def test_proposal_reads_nothing(self):
        result = self.service.propose("demo-a", "chat-a", "Current")
        self.assertEqual(result["status"], "account_proposal")
        self.assertEqual(self.accounts.reads, [])
        self.assertEqual(len(self.calls), 1)

    def test_confirmed_proposal_reads_once_without_another_model_call(self):
        p = self.service.propose("demo-a", "chat-a", "Current")
        result = self.service.confirm("demo-a", "chat-a", p["proposal_token"])
        self.assertEqual(result["status"], "transactions")
        self.assertEqual(self.accounts.reads, ["A-CURRENT"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.service.confirm("demo-a", "chat-a", p["proposal_token"])["status"], "proposal_changed")

    def test_retirement_after_proposal_refuses_the_confirmed_read(self):
        p = self.service.propose("demo-a", "chat-a", "Current")
        self.accounts.retire("A-CURRENT")
        self.assertEqual(self.service.confirm("demo-a", "chat-a", p["proposal_token"])["status"], "stale_options")
        self.assertEqual(self.accounts.reads, [])

    def test_new_proposal_retires_previous_token(self):
        p = self.service.propose("demo-a", "chat-a", "Current")
        self.service.propose("demo-a", "chat-a", "Again")
        self.assertEqual(self.service.confirm("demo-a", "chat-a", p["proposal_token"])["status"], "proposal_changed")

    def test_different_conversation_cannot_consume_a_proposal(self):
        p = self.service.propose("demo-a", "chat-a", "Current")
        self.assertEqual(self.service.confirm("demo-a", "chat-b", p["proposal_token"])["status"], "proposal_changed")

    def test_different_owner_cannot_consume_a_proposal(self):
        p = self.service.propose("demo-a", "chat-a", "Current")
        self.assertEqual(self.service.confirm("demo-b", "chat-a", p["proposal_token"])["status"], "proposal_changed")

    def test_cancel_reads_nothing_and_retires_token(self):
        p = self.service.propose("demo-a", "chat-a", "Current")
        self.assertEqual(self.service.cancel("demo-a", "chat-a", p["proposal_token"])["status"], "proposal_cancelled")
        self.assertEqual(self.service.confirm("demo-a", "chat-a", p["proposal_token"])["status"], "proposal_changed")
        self.assertEqual(self.accounts.reads, [])
