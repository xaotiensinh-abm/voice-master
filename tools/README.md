# Tools — cấp phép (author only)

Bộ công cụ để **tác giả** cấp License Key cho máy của khách. Chạy bằng Python có
`cryptography` (dùng venv backend: `backend/.venv/Scripts/python.exe`).

> ⚠️ **KHÔNG commit private key.** `tools/keys/` đã được .gitignore. Mất private key =
> phải đổi key mới và toàn bộ license cũ vô hiệu.

## 1. Tạo keypair (một lần duy nhất)
```powershell
backend\.venv\Scripts\python.exe tools\license_keygen.py
```
- Ghi `tools/keys/private.pem` (giữ bí mật).
- In ra dòng `PUBLIC_KEY_B64 = "..."` → **dán vào** `backend/services/license_core.py`
  (hằng `PUBLIC_KEY_B64`). Đổi key = phải build lại app.

## 2. Cấp license cho một máy
Khách gửi **Mã máy** (xem trong app, tab *Bản quyền*, dạng `XXXX-XXXX-XXXX-XXXX`).
```powershell
backend\.venv\Scripts\python.exe tools\license_gen.py --machine-code XXXX-XXXX-XXXX-XXXX
# Có hạn:   --exp 2027-06-26
# Hạng:     --tier std
```
- In ra **License Key** (`VM1....`). Gửi cho khách → khách dán vào tab *Bản quyền* → **Kích hoạt**.
- Key chỉ chạy đúng máy có mã đó; máy khác sẽ bị từ chối.

## 3. Lưu ý
- Trial mặc định **7 ngày**/máy (đổi qua env `VOICE_MASTER_TRIAL_DAYS` khi build nếu cần).
- Enforcement chỉ bật trong bản .exe (`VOICE_MASTER_LICENSE_ENFORCED=1`); chạy từ source = demo (không khoá).
- Chi tiết kỹ thuật: [../docs/licensing-packaging-spec.md](../docs/licensing-packaging-spec.md).
