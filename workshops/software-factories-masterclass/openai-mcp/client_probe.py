"""List and call the stub reviewer over a real MCP session, as Mantle's list_tools would."""
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:8941/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print("tools:", [t.name for t in tools], "outputSchema published:", [t.outputSchema is not None for t in tools])
            for text in ("someone used my card, I did not make this payment", "I am checking my statement"):
                result = await session.call_tool("ask_reviewer", {"description": text})
                print("structured:", json.dumps(result.structuredContent, sort_keys=True))


asyncio.run(main())
