"""Transport identity boundary; no model arguments can select an owner."""
from collections.abc import Mapping

SENDER_META = "rasa.briefing.sender_id"


class IdentityRefused(ValueError):
    """The authenticated transport cannot establish conversation ownership."""


def conversation_identity(authenticated_peer: str | None, metadata: Mapping | None) -> tuple[str, str]:
    """Use only a peer established by transport authentication.

    The caller must not derive authenticated_peer from HTTP/MCP headers or
    tool arguments without verifying their credential. Metadata by itself is
    not authentication. A transport session ID is not a conversation ID.
    """
    if not isinstance(metadata, Mapping):
        raise IdentityRefused("conversation_identity_required")
    sender = metadata.get(SENDER_META)
    for value in (authenticated_peer, sender):
        if (not isinstance(value, str) or not value.strip() or len(value) > 200
                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise IdentityRefused("conversation_identity_required")
    return authenticated_peer, sender
