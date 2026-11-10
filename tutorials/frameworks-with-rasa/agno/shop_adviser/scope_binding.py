"""Public demo routing; replace the registry with authenticated channel identity."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerScope:
    user_id: str
    session_id: str


# These senders are synthetic public fixtures, not a customer login mechanism.
# Production channels must resolve a principal after authentication themselves.
DEMO_SCOPES = {
    "willow-a-chat": CustomerScope("customer-a", "a-chat"),
    "willow-a-voice": CustomerScope("customer-a", "a-voice"),
    "willow-b-chat": CustomerScope("customer-b", "b-chat"),
}


def resolve_demo_scope(sender_id: str) -> CustomerScope | None:
    if not isinstance(sender_id, str):
        return None
    return DEMO_SCOPES.get(sender_id)
