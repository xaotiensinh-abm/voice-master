# Kế hoạch — Đóng gói, HDSD, đẩy GitHub để chia sẻ (agent tự setup)

> Trạng thái: ✅ ĐÃ TRIỂN KHAI (P1–P7, bỏ P8 theo lựa chọn). Repo:
> https://github.com/xaotiensinh-abm/voice-master (Private). Đã verify clone sạch → `uv sync` → app boot OK.
> Mục tiêu: bạn bè clone repo → **đưa cho agent của họ** → agent tự cài đặt đầy đủ,
> **chạy backend ngầm trên PC** (không phụ thuộc phiên agent) → kết nối MCP và tự dùng.

## 0. Yêu cầu cốt lõi đã chốt
- **Backend chạy ngầm như tiến trình độc lập trên PC** — không chết khi shell/phiên agent đóng.
- Agent chỉ cần đọc 1 file hướng dẫn + chạy 1 script là setup xong.
- Không commit thứ nặng/bí mật (đã có .gitignore tốt: `.venv`, `node_modules`, `models/`, `*.db`, `.env`).

## 1. Backend chạy ngầm (persistent background) — KHẮC PHỤC vấn đề "chết theo phiên"

Hiện uvicorn chạy foreground/trong shell agent → tắt khi phiên đóng. Cần tiến trình **detached**.

- `scripts/start_backend_detached.ps1`: dùng `Start-Process` + **`pythonw.exe`** của venv để chạy
  `uvicorn main:app --host 127.0.0.1 --port 8757` **không cửa sổ, tách hẳn** shell cha →
  sống độc lập. Ghi PID vào `runtime.json` (backend đã tự ghi). In ra URL MCP.
- `scripts/stop_backend.ps1`: đọc PID từ `runtime.json` (hoặc theo cổng 8757) → `Stop-Process`.
- `scripts/status_backend.ps1`: gọi `GET /health` báo đang chạy/tắt.
- (Tùy chọn) `scripts/install_autostart.ps1`: tạo **Scheduled Task** chạy start lúc đăng nhập Windows.

**Acceptance:** chạy start script rồi đóng terminal → `GET /health` vẫn 200; MCP `/mcp` vẫn kết nối.
**Test:** start → đóng shell gọi nó → curl health 200 → stop → health 000.

## 2. Agent tự setup (1 file + 1 script)

- `AGENT_SETUP.md` — hướng dẫn NGẮN, theo bước cho agent:
  1. Yêu cầu sẵn có: Windows + Python 3.12 + (Node 18+ nếu muốn UI) + `uv`.
  2. `cd backend; uv sync` (tạo `.venv` từ `uv.lock`, cài deps gồm vieneu, huggingface_hub…).
  3. Chạy `scripts/start_backend_detached.ps1` (backend chạy ngầm).
  4. Gọi MCP `ensure_model_ready` (tải model VieNeu ~700MB lần đầu) — chờ `downloaded=true`.
  5. Kết nối MCP **Streamable HTTP** `http://127.0.0.1:8757/mcp` → dùng `synthesize`→`wait_for_job`→`download_job_audio`.
- `scripts/setup.ps1` — gộp B1–B3: kiểm tra/cài `uv` (winget/pip), `uv sync`, start detached, in URL MCP.
  → agent chỉ chạy **một lệnh**.

**Acceptance:** trên máy sạch (đã có Python+uv), agent theo `AGENT_SETUP.md` → backend ngầm + tạo được audio.

## 3. Đóng gói (2 hướng)

- **Hướng A — Repo + agent (CHÍNH, cho chia sẻ):** đẩy mã nguồn lên GitHub + `AGENT_SETUP.md` +
  scripts. Nhẹ, không kèm model/venv. uv lo môi trường; model tự tải lần đầu. Đây là cách bạn bè
  "đưa cho agent là xong".
- **Hướng B — Bản desktop Electron portable (TÙY CHỌN, cho người không dùng agent):**
  `pnpm build` → `electron-builder --dir` (đã cấu hình `win.target=dir`). Cần bundle **Python portable +
  backend** (đã có hướng trong `scripts/build_portable.ps1`) để double-click chạy. Nặng hơn; model vẫn
  tải lần đầu. Làm sau nếu cần.

## 4. Tài liệu HDSD

- `README.md` (tiếng Việt, ở gốc repo): app là gì; 2 cách dùng (Agent / App desktop); yêu cầu hệ thống;
  quick start; link tới các doc; ảnh/chức năng chính.
- `AGENT_SETUP.md`: cho agent (mục 2).
- `docs/huong-dan-su-dung.md`: HDSD chi tiết cho người dùng app desktop (tạo voice, chèn cảm xúc,
  tải/quản lý model, settings, trang Kết nối Agent/API).
- Đã có sẵn: `docs/agent-api.md` (hợp đồng API/MCP + cảm xúc), `docs/agent-api-plan.md`.

## 5. Đẩy GitHub

- Audit `.gitignore` (đã tốt) + thêm `README.md` + `LICENSE` (MIT?).
- Kiểm tra **không có secret** trong repo (API key ElevenLabs nằm ở AppData/DB — ngoài repo; xác nhận).
- `git add` + commit đầu tiên (repo hiện chưa có commit) → tạo repo bằng `gh repo create` → push.
- Xác nhận với chủ repo: **tên repo, public/private, tài khoản gh**.
- Sau push: **clone thử ra thư mục tạm**, chạy `setup.ps1`, xác nhận backend ngầm + 1 vòng synth OK
  (chứng minh "người khác clone về dùng được").

## 6. Task breakdown
- **P1** scripts chạy ngầm: start_detached / stop / status (+autostart tùy chọn). Test đóng-shell-vẫn-sống.
- **P2** `setup.ps1` + `AGENT_SETUP.md` (agent 1-lệnh).
- **P3** `README.md` (gốc) — giới thiệu + quick start 2 hướng.
- **P4** `docs/huong-dan-su-dung.md` — HDSD app desktop chi tiết.
- **P5** Audit repo trước push: .gitignore, secret scan, LICENSE, dọn file rác (vd `vite.config.web.ts` giữ lại, `extracted/` đã ignore).
- **P6** Tạo repo GitHub + push (CẦN xác nhận tên/visibility).
- **P7** Verify fresh-clone: clone tạm → setup.ps1 → health 200 + 1 vòng synth qua /mcp.
- **P8 (tùy chọn)** Bản Electron portable (Hướng B) + mục HDSD cài đặt bản desktop.

## 7. Câu hỏi cần chốt trước khi làm
- Tên repo GitHub + **public hay private**? Tài khoản `gh` đã đăng nhập chưa?
- Có làm luôn **bản desktop Electron portable** (P8) hay chỉ repo-cho-agent?
- Có cần **tự khởi động backend lúc đăng nhập Windows** (Scheduled Task) không?
- Giấy phép: MIT hay để trống?
