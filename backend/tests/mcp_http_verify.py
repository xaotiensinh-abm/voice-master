"""Verify the Streamable HTTP MCP transport (modern, what most agents use).

Run against a live backend:
    .venv/Scripts/python.exe tests/mcp_http_verify.py
"""

from __future__ import annotations

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HTTP_URL = "http://127.0.0.1:8757/mcp"


async def main() -> int:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(HTTP_URL) as (read, write, *_rest):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("TOOLS:", names)

            res = await session.call_tool("get_model_status", {})
            text = "".join(c.text for c in res.content if getattr(c, "type", None) == "text")
            print("get_model_status ->", text[:200])

            ok = "synthesize" in names and '"downloaded"' in text
            print("STREAMABLE_HTTP_OK" if ok else "STREAMABLE_HTTP_FAIL")
            return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
