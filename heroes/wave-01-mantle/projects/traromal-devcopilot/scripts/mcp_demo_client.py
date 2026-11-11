#!/usr/bin/env python3
"""Client test for the DevPilot MCP demo server.

Proves the full Model Context Protocol round-trip over Streamable HTTP:
initialize -> tools/list -> tools/call.
"""
import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client


async def main():
    url = "http://127.0.0.1:8000/mcp"
    async with streamablehttp_client(url) as (read, write, get_session_id):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("INITIALIZED:", init.serverInfo.name, init.serverInfo.version)

            tools = await session.list_tools()
            print("TOOLS LISTED:")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description.splitlines()[0]}")

            print("\nCALL check_license_seats('sentry') ...")
            res = await session.call_tool(
                "check_license_seats", {"product": "sentry"}
            )
            for c in res.content:
                print("  RESULT:", c.text)

            print("\nCALL check_license_seats('jetbrains-ultimate') ...")
            res = await session.call_tool(
                "check_license_seats", {"product": "jetbrains-ultimate"}
            )
            for c in res.content:
                print("  RESULT:", c.text)

            print("\nCALL get_system_time() ...")
            res = await session.call_tool("get_system_time", {})
            for c in res.content:
                print("  RESULT:", c.text)


if __name__ == "__main__":
    asyncio.run(main())
