"""Client probe for the minimal MCP spike - proves the full client path.

Client -> MCP endpoint -> JSON-RPC 2.0 -> tool discovery -> tool invocation
-> real result. Requires mcp_servers.spike to be running on port 8090.
"""

from __future__ import annotations

import asyncio
import json

from mcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8090/mcp") as client:
        print(f"protocol: {client.protocol_version}")
        print(f"server:   {client.server_info}")

        tools = await client.list_tools()
        names = [t.name for t in tools.tools]
        print(f"tools:    {names}")

        result = await client.call_tool("health_check", {"service": "auth-api"})
        print(f"call:     health_check(auth-api)")

        for item in result.content:
            if item.type == "text":
                payload = json.loads(item.text)
                print(f"result:   {payload['status']} (http {payload['http_code']}, uptime {payload['uptime_seconds']}s)")
        print("SPIKE OK")


if __name__ == "__main__":
    asyncio.run(main())