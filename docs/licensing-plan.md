# Kế hoạch — License: Trial 7 ngày → Kích hoạt theo mã máy (offline)

> Trạng thái: PLAN (chưa code). Mô hình: **kích hoạt offline, chữ ký số Ed25519, khoá theo máy**.
> Không cần license server. Tác giả giữ **private key**; app chỉ chứa **public key**.

## 0. Luồng tổng quan
1. Lần chạy đầu → bắt đầu **Trial 7 ngày** (tự động, không cần làm gì).
2. Trong app hiện **Mã máy (Machine Code)** — chuỗi ngắn duy nhất theo máy.
3. Hết trial → app khoá việc tạo voice, hiện ô nhập **Mã đăng ký (License Key)**.
4. User gửi **Mã máy** cho tác giả (ĐT/Zalo) → tác giả chạy **công cụ sinh key** (offline, có private key)
   → trả về **License Key** (đã ký, gắn đúng mã máy đó).
5. User dán License Key vào app → app **xác minh chữ ký + đúng máy** → mở khoá vĩnh viễn (hoặc tới hạn).

```
[Lần đầu] → TRIAL (≤7 ngày) ──hết hạn──► EXPIRED ──nhập key hợp lệ──► LICENSED
                                  ▲                                      │
                                  └──────────── key sai/khác máy ────────┘
```

## 1. Cơ chế kỹ thuật (đã xác minh khả thi: `cryptography` Ed25519, Windows MachineGuid)
- **Machine ID:** hash (SHA-256) của `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` (+ tuỳ chọn volume serial).
  Hiển thị **Machine Code** = base32 rút gọn (~16–20 ký tự, chia nhóm dễ đọc/đọc qua ĐT).
- **License Key:** `base64url(payload || signature)`, trong đó
  `payload = {machine_id, exp?, tier, issued_at}` ký bằng **Ed25519 private key** của tác giả.
  App xác minh bằng **public key nhúng sẵn** + kiểm tra `machine_id == máy hiện tại` + `exp` chưa qua.
  → Không thể giả mạo key (thiếu private key), không thể dùng key của máy A cho máy B.

## 2. Lưu trữ trạng thái (trong NEO_VOICE_HOME, ngoài repo)
- **Trial record** (ký số chống sửa tay): `{first_run, trial_days}` + một marker phụ ở **registry**.
  `effective_start = min(các marker tìm được)` → chống xoá file để "trial lại" (mức cơ bản).
- **License**: lưu nguyên License Key (tự chứa + ký), xác minh lại mỗi lần khởi động.

## 3. Thành phần & Task

### L1 — Lõi crypto + keygen (nền tảng)
`backend/services/license_core.py`: hàm `verify_key(key, machine_id) -> {ok, payload, reason}` dùng public key nhúng.
Script `tools/license_keygen.py` tạo cặp khoá Ed25519 (chạy 1 lần). **Private key KHÔNG commit** (gitignore `tools/keys/`).
- Test: ký/verify hợp lệ; sai chữ ký → fail; sai machine_id → fail; quá `exp` → fail.

### L2 — Machine ID & Machine Code
`backend/services/machine_id.py`: lấy MachineGuid → SHA-256 → `machine_id` (hex) + `machine_code` (base32 nhóm).
- Test: ổn định qua nhiều lần gọi; định dạng code đúng.

### L3 — Trial tracking
`backend/services/trial.py`: tạo/đọc trial record (ký), marker registry, tính `days_left`, `expired`.
- Test: lần đầu → 7 ngày; giả lập first_run lùi 8 ngày → expired; xoá file nhưng còn registry → vẫn tính đúng.

### L4 — License service (state machine)
`backend/services/license_service.py`: `status() -> {state, days_left, machine_code, exp?}` với
`state ∈ {trial, licensed, expired, invalid}`; `activate(key)` → verify + lưu, trả kết quả.
- Test: các nhánh trial/licensed/expired/invalid.

### L5 — Backend endpoints + error code
`routers/license.py`: `GET /license/status`, `POST /license/activate {key}`. Thêm vào `/health` tóm tắt license.
Error code mới: `LICENSE_REQUIRED` (hết trial, chưa kích hoạt), `LICENSE_INVALID`.
- Test: TestClient status/activate; activate key hợp lệ (ký bằng key test) → licensed.

### L6 — Chốt chặn (enforcement) — điểm duy nhất
Chặn tại **tạo job** (`routers/tts.create_job`) — dùng chung cho REST **và** MCP `synthesize`.
Khi không (TRIAL còn hạn hoặc LICENSED) → trả `LICENSE_REQUIRED` kèm `machine_code`, `days_left`.
- Test: trial còn hạn → tạo job OK; expired → 402/403 `LICENSE_REQUIRED`; licensed → OK.

### L7 — Công cụ sinh key cho tác giả
`tools/license_gen.py`: nhập `machine_code` (+ `--exp`, `--tier`) → in **License Key**. Dùng private key local.
`tools/README.md`: HOWTO cho tác giả (giữ private key an toàn, quy trình cấp key).
- Acceptance: tác giả tạo key từ machine_code của user → user kích hoạt thành công.

### L8 — Frontend
- Trang **"Bản quyền / Kích hoạt"** (sidebar): hiện trạng thái (Trial còn N ngày / Đã kích hoạt / Hết hạn),
  **Machine Code** (nút Copy), ô dán License Key + nút Kích hoạt.
- **Badge trial** ở sidebar footer ("Dùng thử: còn N ngày").
- **Chặn nút Tạo MP3** khi expired + dẫn tới trang kích hoạt. Surfacing lỗi `LICENSE_REQUIRED` từ MCP/REST.
- Test: build + hiển thị 3 trạng thái.

### L9 — Tài liệu
README/HDSD/AGENT_SETUP: giải thích trial 7 ngày, cách lấy Machine Code, gửi cho tác giả lấy key, kích hoạt.

### L10 — Kiểm thử tổng + verify
Unit (L1–L4) + integration: giả lập trial→expire→activate; xác nhận gate chặn synth khi hết hạn (cả MCP).
`pytest -q` xanh, không hồi quy.

## 4. Chiến lược phát hành (ĐÃ CHỐT)
- **Repo GitHub = bản DEMO/test** (public): chạy từ source, **license KHÔNG bắt buộc** (cờ tắt) để dễ test/đóng góp.
- **Sản phẩm thật = file .exe đóng gói**: **license BẬT**, enforcement nhúng trong build.
- Cờ điều khiển: `VOICE_MASTER_LICENSE_ENFORCED` (mặc định **false** ở dev/source, **true** trong build .exe).
- Vì bản phát hành là .exe (đã build/khó sửa), source public không làm yếu license của sản phẩm bán ra.

## 5. Đóng gói .exe (track song song — xem §6 task K*)
- **Tận dụng:** VieNeu v3 Turbo có đường **CPU torch-free qua ONNX Runtime** → build **CPU-only nhẹ** (không kèm torch/CUDA),
  phù hợp chia sẻ rộng. (Bản GPU kèm torch rất nặng — để tuỳ chọn sau.)
- Electron (`electron-builder`) đóng gói UI + tự spawn backend; backend đi kèm **Python portable + vieneu(min)+onnxruntime**.
- Mô hình VieNeu vẫn **tải lần đầu** (không nhúng vào .exe để gọn).
- Đầu ra: thư mục portable hoặc **setup .exe (NSIS)**.

## 6. Task đóng gói (K*)
- **K1** Cấu hình build: cờ `LICENSE_ENFORCED`, tách profile dev (off) vs release (on).
- **K2** Bundle backend CPU-only: Python portable + `vieneu`(minimal)+onnxruntime, bỏ torch; script build.
- **K3** electron-builder: nhúng backend + scripts, electron tự khởi động backend (đã có sẵn logic), tạo bản portable.
- **K4** (tuỳ chọn) Installer NSIS (.exe setup) + icon + shortcut.
- **K5** Verify trên máy "sạch" (không cài Python): cài .exe → chạy → tải model → tạo voice → license gate hoạt động.

## 7. Câu hỏi còn lại cần chốt
1. License **vĩnh viễn theo máy** hay **có hạn** (vd 1 năm)?
2. Khi hết hạn: chỉ **chặn tạo voice** hay **khoá toàn bộ**?
3. Kích hoạt: **dán chuỗi key** hay **file .lic**?
4. Đóng gói: **bản portable (thư mục/zip)** hay **setup .exe (NSIS)**? Build **CPU-only** (khuyến nghị) hay kèm GPU?
