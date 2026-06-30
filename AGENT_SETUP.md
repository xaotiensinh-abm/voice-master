# AGENT_SETUP — Hướng dẫn cho Agent tự cài đặt & sử dụng Voice-Master

> Đưa file này cho agent của bạn. Agent đọc và tự làm theo để cài đặt đầy đủ rồi
> tự tạo giọng nói. Backend chạy **ngầm trên máy** (không phụ thuộc phiên agent).

## Yêu cầu sẵn có (prerequisites)
- Windows 10/11
- **Python 3.12** (https://www.python.org/downloads/)
- **uv** — nếu chưa có, `scripts\setup.ps1` sẽ tự cài (qua winget hoặc pip)
- (Tùy chọn, chỉ cần nếu muốn mở giao diện) Node.js 18+ và `pnpm`

## Cài đặt — 1 lệnh
Mở PowerShell tại thư mục dự án rồi chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1        # CPU/ONNX (mọi máy)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Gpu   # + CUDA torch (máy NVIDIA)
```

Script này sẽ: (1) cài `uv` + `ffmpeg` nếu thiếu → (2) `uv sync` cài dependencies backend
(vieneu, onnxruntime…) vào `backend\.venv` → (3) khởi động backend **chạy ngầm** tại
`http://127.0.0.1:8757`. Mặc định **CPU/ONNX** (chạy mọi máy); `-Gpu` cài CUDA torch để dùng GPU NVIDIA.

(Tùy chọn) Tự khởi động backend mỗi lần đăng nhập Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
```

## Tải mô hình lần đầu (~700MB)
Backend đã chạy nhưng mô hình VieNeu tải lần đầu. Agent gọi MCP tool **`ensure_model_ready`**
rồi poll **`get_model_status`** tới khi `downloaded = true` (hoặc mở UI bấm tải).

## Kết nối MCP & vòng lặp tạo voice
- **Endpoint (khuyến nghị): Streamable HTTP** `http://127.0.0.1:8757/mcp`
- Vòng lặp: `synthesize` → `wait_for_job` → `download_job_audio` → lặp với kịch bản tiếp theo.

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import json

async def call(s, tool, args):
    r = await s.call_tool(tool, args)
    return json.loads(r.content[0].text)

async with streamablehttp_client("http://127.0.0.1:8757/mcp") as (read, write, *_):
    async with ClientSession(read, write) as s:
        await s.initialize()
        await call(s, "ensure_model_ready", {})          # tải model lần đầu
        vid = (await call(s, "list_voices", {}))["voices"][0]["voice_id"]
        for script in scripts:
            job = await call(s, "synthesize", {"text": script, "voice_id": vid, "mode": "story"})
            await call(s, "wait_for_job", {"job_id": job["job_id"], "timeout_sec": 240})
            await call(s, "download_job_audio",
                       {"job_id": job["job_id"], "dest_path": r"C:\\out\\%s.mp3" % job["job_id"]})
```

- Hợp đồng API đầy đủ + **cách chèn cảm xúc vào kịch bản**: [docs/agent-api.md](docs/agent-api.md).
- Chỉ chạy localhost, không cần API key.

## Quản lý backend ngầm
```powershell
powershell -ExecutionPolicy Bypass -File scripts\status_backend.ps1   # kiểm tra
powershell -ExecutionPolicy Bypass -File scripts\start_backend_detached.ps1  # bật
powershell -ExecutionPolicy Bypass -File scripts\stop_backend.ps1     # tắt
```

## Sự cố thường gặp
- `httpx.ReadError` khi nối MCP: dùng **Streamable HTTP** `http://127.0.0.1:8757/mcp` (đừng dùng `/mcp/sse` cũ).
- `MODEL_NOT_READY`: gọi `ensure_model_ready` rồi đợi `downloaded=true`.
- Cổng 8757 không phản hồi: chạy `scripts\status_backend.ps1`, nếu DOWN thì `start_backend_detached.ps1`.
