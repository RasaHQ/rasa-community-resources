# SPDX-License-Identifier: MIT
"""Private loopback host transport packaged with native bindings."""
from urllib.parse import urlsplit
import httpx

MAX_BODY = 1_048_576


def origin(value):
    parts=urlsplit(value)
    if parts.scheme!='http' or parts.hostname!='127.0.0.1' or parts.username or parts.password or parts.path not in {'','/'} or parts.query or parts.fragment or parts.port is None:
        raise ValueError('loopback_origin_required')
    return value.rstrip('/')


class HostClient:
    def __init__(self,url,capability):
        self.url=origin(url)
        self._capability=capability

    def control(self,action,**data):
        # All callers are the trusted channel adapter, not model arguments.
        with httpx.Client(trust_env=False,timeout=8,follow_redirects=False) as client:
            response=client.post(self.url+'/host/'+action,json=data,
                headers={'Authorization':'Bearer '+self._capability})
        if response.status_code!=200 or len(response.content)>MAX_BODY:
            raise ValueError('private_host_unavailable')
        return response.json()

    async def call(self,credential,name,arguments):
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
        def local_http(headers=None,timeout=None,auth=None):
            return httpx.AsyncClient(headers=headers,timeout=timeout,auth=auth,trust_env=False,follow_redirects=False)
        async with streamablehttp_client(self.url+'/mcp',headers={'Authorization':'Bearer '+credential},httpx_client_factory=local_http) as streams:
            async with ClientSession(streams[0],streams[1]) as session:
                await session.initialize()
                result=await session.call_tool(name,arguments)
                if result.isError:raise ValueError('service_refused')
                if result.structuredContent is not None:return result.structuredContent
                import json
                return json.loads(result.content[0].text)
