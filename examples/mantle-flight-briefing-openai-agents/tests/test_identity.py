"""Keyless boundary controls; not a Mantle runtime propagation proof."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.identity import IdentityRefused, SENDER_META, conversation_identity


class IdentityControls(unittest.TestCase):
    def test_metadata_without_authenticated_transport_is_refused(self):
        with self.assertRaises(IdentityRefused):
            conversation_identity(None, {SENDER_META: "conversation-a"})

    def test_model_identity_fields_cannot_supply_engine_identity(self):
        with self.assertRaises(IdentityRefused):
            conversation_identity("mantle-peer", {"user_id": "a", "session_id": "a"})

    def test_missing_and_malformed_metadata_refuse(self):
        for metadata in (None, [], {}, {SENDER_META: ""}, {SENDER_META: "a\nb"}):
            with self.assertRaises(IdentityRefused):
                conversation_identity("mantle-peer", metadata)

    def test_both_peer_and_conversation_participate_in_ownership(self):
        a = conversation_identity("peer-a", {SENDER_META: "conversation-a"})
        b = conversation_identity("peer-a", {SENDER_META: "conversation-b"})
        foreign_peer = conversation_identity("peer-b", {SENDER_META: "conversation-a"})
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, foreign_peer)
        self.assertEqual(a, ("peer-a", "conversation-a"))


if __name__ == "__main__":
    unittest.main()
