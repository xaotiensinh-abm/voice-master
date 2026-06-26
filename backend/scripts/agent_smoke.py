"""Manual smoke test — drive the real MCP agent loop against a live backend.

Requires the backend running on 127.0.0.1:8757 with the VieNeu model downloaded
(this performs REAL synthesis on the local engine). Produces 2 mp3 files in a
temp dir to prove the loop works end-to-end.

    .venv/Scripts/python.exe scripts/agent_smoke.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SSE_URL = "http://127.0.0.1:8757/mcp/sse"

SCRIPTS = [
    "Xin chào, đây là kịch bản số một do agent tạo tự động.",
    "Và đây là kịch bản số hai, được tạo ngay sau kịch bản đầu tiên.",
]


async def main() -> int:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    out_dir = Path(tempfile.mkdtemp(prefix="agent_smoke_"))
    print("Output dir:", out_dir)

    async with sse_client(SSE_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call(tool: str, args: dict) -> dict:
                res = await session.call_tool(tool, args)
                text = "".join(c.text for c in res.content if getattr(c, "type", None) == "text")
                return json.loads(text)

            # 1. Pick a VieNeu voice
            voices = await call("list_voices", {})
            voice_id = next(v["voice_id"] for v in voices["voices"] if v["engine"] == "vieneu")
            print("Using voice:", voice_id)

            # 2. Ensure model ready (no wait — already downloaded on this machine)
            print("model:", await call("ensure_model_ready", {}))

            saved = []
            for i, script in enumerate(SCRIPTS, 1):
                created = await call("synthesize", {"text": script, "voice_id": voice_id, "mode": "story"})
                if "error_code" in created:
                    print("synthesize error:", created)
                    return 1
                job_id = created["job_id"]
                print(f"[{i}] job {job_id} → waiting...")

                final = await call("wait_for_job", {"job_id": job_id, "timeout_sec": 240, "poll_sec": 2})
                if final.get("status") != "completed":
                    print(f"[{i}] not completed:", final)
                    return 1

                dest = out_dir / f"script_{i}.mp3"
                dl = await call("download_job_audio", {"job_id": job_id, "dest_path": str(dest)})
                print(f"[{i}] saved {dl.get('saved_path')} ({dl.get('bytes')} bytes)")
                if not dest.exists() or dest.stat().st_size < 1024:
                    print(f"[{i}] FAIL: file missing/too small")
                    return 1
                saved.append(dest)

            print(f"SMOKE_OK — {len(saved)} files generated in a loop")
            return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
