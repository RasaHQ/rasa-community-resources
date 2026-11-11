"""Trusted host wrapper. Never export these methods as model-callable tools.

This proves capability transport, not how a native channel authenticates a user
or observes confirmation. In a teaching run callers are explicitly simulated.
"""

from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class HostSession:
    credential: str = field(repr=False)


class HostClient:
    def __init__(self, base_url, host_capability):
        parts = urlsplit(base_url)
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1"
                or parts.username is not None or parts.password is not None
                or parts.path not in {"", "/"} or parts.query or parts.fragment
                or parts.port is None):
            raise ValueError("host endpoint must be an explicit IPv4 loopback origin")
        self.base_url = base_url.rstrip("/")
        self._capability = host_capability

    def _host(self, action, body):
        try:
            with httpx.Client(trust_env=False, timeout=5, follow_redirects=False) as client:
                response = client.post(self.base_url + "/host/" + action, json=body,
                                       headers={"Authorization": "Bearer " + self._capability})
            if response.status_code != 200:
                raise ValueError("host_control_refused")
            return response.json()
        except Exception:
            raise ValueError("host_control_unavailable_or_refused") from None

    def open_session(self, caller="demo-A"):
        return HostSession(self._host("open", {"caller": caller})["credential"])

    def confirm(self, session, review, exact_transfer):
        """Only call after a genuine deterministic user-confirmation event.

        This host capability is not proof that an upstream model understood yes
        or no. Native flow/channel provenance still requires an integration test.
        """
        return self._host("confirm", {"credential": session.credential,
                                      "review": review, "transfer": exact_transfer})

    def cancel(self, session, review):
        return self._host("cancel", {"credential": session.credential, "review": review})

    def reset(self, session):
        return self._host("reset", {"credential": session.credential})

    async def call(self, session, tool, arguments):
        try:
            return await self._call(session, tool, arguments)
        except Exception:
            raise ValueError("mcp_call_unavailable_or_refused") from None

    async def _call(self, session, tool, arguments):
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        def local_http(headers=None, timeout=None, auth=None):
            return httpx.AsyncClient(headers=headers, timeout=timeout, auth=auth,
                                     trust_env=False, follow_redirects=False)

        async with streamablehttp_client(
            self.base_url + "/mcp",
            headers={"Authorization": "Bearer " + session.credential},
            httpx_client_factory=local_http,
        ) as streams:
            async with ClientSession(streams[0], streams[1]) as client:
                await client.initialize()
                return await client.call_tool(tool, arguments)
