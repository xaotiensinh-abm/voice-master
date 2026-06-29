# Đóng gói .exe (CPU-only, có license)

Tạo bản phát hành Windows: Electron + backend Python portable (CPU-only, ONNX, **không torch**)
+ ffmpeg, license **bật sẵn** (`VOICE_MASTER_LICENSE_ENFORCED=1`). Model VieNeu tải lần đầu khi chạy.

## Yêu cầu trên máy build
- Windows 10/11, **Node 18+** + `pnpm`, **mạng** (tải Python embeddable, pip deps, ffmpeg).
- (Không cần Python cài sẵn — script tự tải Python portable.)

## Build — 1 lệnh
```powershell
# Bản portable (thư mục chạy ngay)
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1

# Hoặc bản cài đặt NSIS (.exe setup + shortcut)
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Installer
```
Kết quả ở `release/`:
- Portable: `release\win-unpacked\Voice-Master.exe` (kèm `python\`, `backend\`, `ffmpeg\` bên cạnh).
- Installer: `release\Voice-Master Setup *.exe`.

## Các bước script làm (scripts\build_backend_runtime.ps1 + build_release.ps1)
1. Tải **Python embeddable** 3.12 → `release-staging\python`, bật site-packages, cài pip.
2. `pip install -r backend\requirements-cpu.txt` (CPU-only, không torch).
3. Tải **ffmpeg** → `release-staging\ffmpeg\ffmpeg.exe`.
4. Copy `backend\` sạch (bỏ `.venv`, cache, tests) → `release-staging\backend`.
5. **Self-check**: import `main` bằng python portable — nếu thiếu module sẽ báo để bổ sung vào `requirements-cpu.txt`.
6. `tsc + vite build + electron-builder` → đóng gói; `extraFiles` đặt `python/backend/ffmpeg` cạnh exe.

## Lúc chạy bản đóng gói
- `electron/main.ts` (khi `app.isPackaged`): spawn `python\python.exe` với
  `VOICE_MASTER_LICENSE_ENFORCED=1` + `VOICE_MASTER_FFMPEG=<...>\ffmpeg\ffmpeg.exe`.
- Backend lên `127.0.0.1:8757`; mở app → tab **Bản quyền** (trial 7 ngày) → tạo voice.

## Gotchas (đọc nếu build/chạy lỗi)
- **Self-check báo thiếu module** → thêm tên package vào `backend\requirements-cpu.txt`, chạy lại.
  (Danh sách hiện tại là best-effort; lần build đầu có thể cần bổ sung 1–2 gói.)
- **`vieneu` kéo torch về (nặng)?** Đảm bảo cài đúng gói tối thiểu `vieneu` (KHÔNG `vieneu[gpu]`).
  Nếu vẫn kéo torch, ghim phiên bản `vieneu` hỗ trợ ONNX/CPU hoặc thêm ràng buộc loại trừ.
- **Tạo MP3 lỗi "ffmpeg không tìm thấy"** → kiểm tra `release-staging\ffmpeg\ffmpeg.exe` tồn tại và
  `extraFiles` đã copy `ffmpeg\` cạnh exe.
- **Model 700MB**: không nhúng — tải lần đầu vào `~/.cache/huggingface`. Cần mạng lần đầu.
- **Đổi public key** (`tools/license_keygen.py`) ⇒ phải build lại app (key cũ vô hiệu).
- Chưa ký số (code signing) → Windows SmartScreen có thể cảnh báo; ký nếu phát hành rộng.

## Verify (K5)
Chạy bản build trên máy **không cài Python**: mở app → backend lên → tải model → tạo voice;
đếm ngày trial; hết hạn → chặn; nhập key (từ `tools\license_gen.py`) → mở khoá.
