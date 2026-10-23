"""Session-start profile lookup for tests. Writes bare project-memory keys."""


class _Memory:
    """Stand-in for Mantle ``ToolContext.memory``."""

    def set(self, key: str, value: str) -> None:
        """Record a project-memory value. No-op in the fixture."""
        del key, value


class _Context:
    """Stand-in for Mantle ``ToolContext``."""

    memory = _Memory()


def load_customer_profile() -> dict[str, str]:
    """Record identity on project memory using a bare key, not project.*."""
    context = _Context()
    context.memory.set("customer_name", "Ada Lovelace")
    return {"ok": "true", "customer_name": "Ada Lovelace"}
