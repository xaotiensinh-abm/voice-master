"""T0 — Verify the existing MCP SSE foundation works end-to-end.

Connects an MCP client to the running backend's /mcp/sse endpoint, lists tools,
and calls list_voices. Run against a live backend on 127.0.0.1:8757:

    .venv/Scripts/python.exe tests/mcp_verify.py
"""

from __future__ import annotations

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SSE_URL = "http://127.0.0.1:8757/mcp/sse"


async def main() -> int:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client(SSE_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("TOOLS:", names)

            async def call(tool: str, args: dict) -> str:
                res = await session.call_tool(tool, args)
                return "".join(c.text for c in res.content if getattr(c, "type", None) == "text")

            voices = await call("list_voices", {})
            print("list_voices ->", voices[:200])

            model = await call("get_model_status", {})
            print("get_model_status ->", model[:200])

            notfound = await call("get_job_status", {"job_id": "job_does_not_exist"})
            print("get_job_status(bogus) ->", notfound[:200])

            expected = {
                "list_voices", "get_model_status", "ensure_model_ready", "synthesize",
                "get_job_status", "wait_for_job", "download_job_audio", "get_history", "cancel_job",
            }
            missing = expected - set(names)
            ok = (
                not missing
                and '"voices"' in voices
                and '"downloaded"' in model
                and '"JOB_NOT_FOUND"' in notfound
            )
            if missing:
                print("MISSING TOOLS:", missing)
            print("FOUNDATION_OK" if ok else "FOUNDATION_FAIL")
            return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
