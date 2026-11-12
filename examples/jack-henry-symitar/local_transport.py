# SPDX-License-Identifier: MIT
"""Bounded loopback-only transport. No bank origin, redirects or retries."""
import asyncio
import httpx
from vendor_client import MAX_BODY, WireResponse
from lib.host_client import HostClient, origin


class LocalTransport:
    def __init__(self, base_url, bearer):
        self.url=origin(base_url)
        self._bearer=bearer

    async def send(self, request):
        async with httpx.AsyncClient(trust_env=False,timeout=5,follow_redirects=False) as client:
            async with client.stream(request.method,self.url+request.path,content=request.body,
                    headers={'Authorization':'Bearer '+self._bearer,'Content-Type':request.media_type}) as response:
                body=bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body)>MAX_BODY:raise ValueError('oversize_response')
                return WireResponse(response.status_code,response.headers.get('content-type','').split(';')[0],bytes(body))
