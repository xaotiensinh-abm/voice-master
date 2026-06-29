# Đóng gói .exe (GPU mặc định, có license)

Tạo bản phát hành Windows: Electron + backend Python portable + ffmpeg, license **bật sẵn**
(`VOICE_MASTER_LICENSE_ENFORCED=1`). **Mô hình KHÔNG nhúng** — khách mở app rồi **bấm nút Tải mô hình**
lần đầu (~700MB, vào `~/.cache/huggingface`).

- **GPU (mặc định):** bundle `torch + torchaudio` (CUDA 12.1). VieNeu dùng PyTorch trên máy có
  GPU NVIDIA; máy không GPU **tự fallback ONNX/CPU**. Bundle nặng (~vài GB).
- **CPU (`-Cpu`):** chỉ ONNX, không torch — nhẹ hơn nhiều, chạy mọi máy (chậm hơn trên máy mạnh GPU).

## Yêu cầu máy build
- Windows 10/11, **Node 18+** + `pnpm`, **mạng** (tải Python embeddable, pip deps, torch CUDA, ffmpeg).
- Không cần Python cài sẵn (script tự tải Python portable).

## Build — 1 lệnh
```powershell
# GPU portable (mặc định)
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1

# CPU-only portable
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Cpu

# GPU + bộ cài NSIS (.exe setup + shortcut)
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Installer
```
Kết quả ở `release/`:
- Portable: `release\win-unpacked\Voice-Master.exe` (kèm `python\`, `backend\`, `ffmpeg\` bên cạnh).
- Installer: `release\Voice-Master Setup *.exe`.

## Script làm gì
1. Tải **Python embeddable** 3.12 → `release-staging\python`, bật site-packages, cài pip.
2. `pip install -r backend\requirements-base.txt` (không torch).
3. **GPU:** `pip install torch torchaudio --index-url .../whl/cu121` (+ kiểm tra `torch.cuda.is_available()`).
4. Tải **ffmpeg** → `release-staging\ffmpeg\ffmpeg.exe`.
5. Copy `backend\` sạch (bỏ `.venv`, cache, tests).
6. **Self-check** import `main` bằng python portable; thiếu module → báo để thêm vào `requirements-base.txt`.
7. `tsc + vite build + electron-builder` → `extraFiles` đặt `python/backend/ffmpeg` cạnh exe.

## Lúc chạy bản đóng gói
- `electron/main.ts` (khi `app.isPackaged`): spawn `python\python.exe` với
  `VOICE_MASTER_LICENSE_ENFORCED=1` + `VOICE_MASTER_FFMPEG=<...>\ffmpeg\ffmpeg.exe`.
- Backend lên `127.0.0.1:8757` → mở app → màn **Tạo giọng nói** hiện nút **Tải mô hình** (lần đầu),
  hoặc tab **Cài đặt → Mô hình**. Tải xong → tạo voice. Tab **Bản quyền**: trial 7 ngày → kích hoạt.

## Gotchas
- **Máy build GPU:** torch CUDA ~2.5GB tải về; bundle cuối vài GB. Khách chạy GPU cần **driver NVIDIA**
  (CUDA runtime đã nằm trong wheel torch — không cần cài CUDA toolkit).
- **torch trong Python embeddable:** hiếm khi lỗi load DLL. Bước "torch import check" sẽ phát hiện sớm.
  Nếu lỗi, cân nhắc build `-Cpu` hoặc dùng python copy đầy đủ thay embeddable.
- **`vieneu` kéo torch CPU từ PyPI?** Ta cài torch CUDA SAU base nên đè đúng bản CUDA; nếu vieneu ghim
  torch CPU, thêm ràng buộc/cài lại torch CUDA sau cùng.
- **Self-check báo thiếu module** → thêm vào `backend\requirements-base.txt`, chạy lại.
- **"ffmpeg không tìm thấy"** → kiểm tra `release-staging\ffmpeg\ffmpeg.exe` + extraFiles copy `ffmpeg\` cạnh exe.
- **Đổi public key** (`tools/license_keygen.py`) ⇒ build lại app (key cũ vô hiệu).
- Chưa ký số → Windows SmartScreen có thể cảnh báo.

## Verify (K5)
Chạy bản build trên máy **không cài Python**: mở app → backend lên → **bấm Tải mô hình** → tạo voice
(GPU dùng PyTorch nếu có NVIDIA, không thì ONNX/CPU); trial đếm ngày; hết hạn → chặn; nhập key → mở khoá.
