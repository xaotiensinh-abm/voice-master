# Voice-Master — Local Vietnamese TTS

Ứng dụng chuyển văn bản thành giọng nói tiếng Việt, chạy **hoàn toàn trên máy** (engine
VieNeu-TTS), kèm **API/MCP** để agent tự động tạo voice theo vòng lặp.

- 🎙 Tạo MP3 từ văn bản hoặc file `.txt`/`.md`, tự chia đoạn cho kịch bản dài rồi ghép lại.
- 🎭 Điều khiển cảm xúc: thẻ inline (`[cười]`, `[thở dài]`…) + tham số `mode`/`emotion`/`speed`.
- 🔌 MCP (Streamable HTTP) cho agent: `synthesize → wait_for_job → download_job_audio`.
- ⬇️ Mô hình tải lần đầu từ HuggingFace (không kèm bộ cài để gọn nhẹ).

## Yêu cầu
- Windows 10/11, **Python 3.12**, **uv** (tự cài nếu thiếu).
- (Chỉ cần cho giao diện desktop) Node.js 18+ và `pnpm`.
- Lần đầu cần mạng để tải mô hình VieNeu (~700MB), sau đó chạy offline.

## Hai cách dùng

### Cách A — Cho agent tự setup (chia sẻ cho bạn bè)
Đưa repo + [AGENT_SETUP.md](AGENT_SETUP.md) cho agent. Agent chạy 1 lệnh:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
→ cài deps, **backend chạy ngầm** ở `http://127.0.0.1:8757`. Agent nối MCP
`http://127.0.0.1:8757/mcp` và tự tạo voice. Chi tiết: [AGENT_SETUP.md](AGENT_SETUP.md),
hợp đồng API: [docs/agent-api.md](docs/agent-api.md).

(Tùy chọn) tự bật backend khi đăng nhập Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
```

### Cách B — Giao diện desktop (cho người dùng thường)
```powershell
# Cửa sổ 1: backend
powershell -ExecutionPolicy Bypass -File scripts\start_backend_detached.ps1
# Cửa sổ 2: giao diện web
pnpm install
pnpm dev:web        # mở http://localhost:5173
```
Hoặc bản Electron: `pnpm dev`. HDSD chi tiết: [docs/huong-dan-su-dung.md](docs/huong-dan-su-dung.md).

## Quản lý backend ngầm
| Lệnh | Tác dụng |
|------|----------|
| `scripts\start_backend_detached.ps1` | Bật backend chạy ngầm (port 8757) |
| `scripts\status_backend.ps1` | Kiểm tra đang chạy/tắt |
| `scripts\stop_backend.ps1` | Tắt backend |
| `scripts\install_autostart.ps1` | Tự bật khi đăng nhập (thêm `-Remove` để gỡ) |

## Tài liệu
- [AGENT_SETUP.md](AGENT_SETUP.md) — agent tự cài đặt & dùng.
- [docs/agent-api.md](docs/agent-api.md) — API/MCP + cách chèn cảm xúc vào kịch bản.
- [docs/huong-dan-su-dung.md](docs/huong-dan-su-dung.md) — HDSD giao diện desktop.

## Kiến trúc (tóm tắt)
- `backend/` — FastAPI (REST `/v1/*`, MCP `/mcp`), engine VieNeu, hàng đợi job tuần tự, chia đoạn + ghép.
- `src/` — giao diện React (tạo voice, quản lý model, trang Kết nối Agent/API).
- `electron/` — vỏ desktop (tự khởi động backend khi đóng gói).

## Bản quyền
MIT — xem [LICENSE](LICENSE).
