"""Worker-only native Agents boundary; importing it never reads a key or calls a provider."""


class UnsupportedAgentsSDK(ValueError):
    """The selected worker SDK cannot make a managed Agents request."""


def require_agents_sessions(client):
    sessions = getattr(getattr(getattr(client, 'beta', None), 'agents', None), 'sessions', None)
    if not callable(getattr(sessions, 'create', None)):
        raise UnsupportedAgentsSDK('The worker SDK lacks client.beta.agents.sessions; use its locked environment.')


def native_turn(client, *, agent, text, handlers=None, invoke=None, max_calls=16):
    """Start a fresh bounded session; Core owns collection, guards and turn success.

    Revisions must carry the prior validated brief in text, never reuse a native
    session with the legacy stream-per-post API. SDK-native callbacks have no
    call id; this boundary does not claim application-level call-id deduplication.
    """
    require_agents_sessions(client)
    if invoke is None:
        from zeo_core.integrations.agents import run_native
        invoke = run_native
    return invoke(client, agent=agent, environment={'type': 'openai_hosted', 'network': {'access': 'disabled'}},
                  text=text, handlers=handlers, max_calls=max_calls, max_events=10000,
                  deadline_seconds=60, timeout=20, spend_limit_cents=200)
