# SPEC — License (Trial 7 ngày → kích hoạt theo máy) + Đóng gói .exe

> Tài liệu kỹ thuật chi tiết (source of truth). Đi cùng [licensing-plan.md](licensing-plan.md).
> Baseline đã chốt: **license vĩnh viễn theo máy · chỉ chặn tạo voice khi hết hạn · kích hoạt bằng
> dán chuỗi key · đóng gói portable CPU-only · enforcement chỉ bật trong bản .exe**.

---

## 1. Mục tiêu & phạm vi

**Mục tiêu**
- Người dùng mới: tự động **Trial 7 ngày**, dùng đầy đủ.
- Hết trial: chặn **tạo voice** cho tới khi nhập **License Key** hợp lệ (gắn đúng máy).
- Kích hoạt **offline** (không cần license server): tác giả ký key bằng private key, app xác minh bằng public key nhúng sẵn.
- Hai hình thái phát hành: **repo demo** (enforcement OFF) và **bản .exe** (enforcement ON).

**Non-goals**
- Không làm license server / tài khoản online.
- Không chống được người sửa **mã nguồn demo** (chấp nhận — bản bán là .exe).
- Không DRM tuyệt đối cho .exe (chỉ nâng rào cản; xem §10 Threat model).

---

## 2. Thuật ngữ & định danh

| Tên | Định nghĩa |
|-----|-----------|
| `machine_id` | `SHA256( MachineGuid + APP_SALT )` → hex. Nội bộ. |
| `machine_code` | Rút gọn của `machine_id` để người dùng đọc/đọc qua ĐT. **Đây là định danh nhúng trong license.** |
| `License Key` | Chuỗi đã ký (Ed25519) chứa `machine_code` + metadata. |
| `APP_SALT` | Hằng số chuỗi nhúng trong app (đổi salt = đổi toàn bộ machine_code). |

**Thuật toán machine_code**
```
guid        = winreg HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid   (fallback: platform.node()+mac)
machine_id  = sha256( (guid + APP_SALT).encode() ).hexdigest()          # 64 hex
raw         = sha256( ("MC:" + machine_id).encode() ).digest()[:10]     # 10 bytes = 80 bit
code        = base32(raw) without padding                               # 16 ký tự A-Z2-7
machine_code= nhóm 4: "XXXX-XXXX-XXXX-XXXX"
```
- Ổn định qua reboot, duy nhất theo máy (đủ thực dụng). Không chứa thông tin nhạy cảm.

---

## 3. Định dạng License Key

**Payload** (JSON compact, sorted keys → bytes UTF-8):
```json
{"v":1,"mc":"XXXX-XXXX-XXXX-XXXX","exp":null,"tier":"std","iat":"2026-06-26"}
```
- `v`: schema version. `mc`: machine_code ràng buộc. `exp`: `null` (vĩnh viễn) hoặc `"YYYY-MM-DD"`. `tier`: hạng (mặc định `std`). `iat`: ngày phát hành.

**Ký & mã hoá**
```
sig = Ed25519_sign(private_key, payload_bytes)            # 64 bytes
key = "VM1." + b64url(payload_bytes) + "." + b64url(sig)  # b64url không padding
```
- Tiền tố `VM1` = version giao thức. Người dùng copy/paste cả chuỗi.

**Xác minh (trong app, dùng public key nhúng)**
1. Tách `VM1.<p>.<s>`; sai định dạng/prefix → `LICENSE_INVALID`.
2. `Ed25519_verify(PUBLIC_KEY, payload_bytes, sig)` sai → `LICENSE_INVALID`.
3. `payload.mc != machine_code` hiện tại → `LICENSE_INVALID` (sai máy).
4. `payload.exp` có và đã qua (so UTC date) → `EXPIRED`.
5. Hợp lệ → `LICENSED`.

---

## 4. Trial & lưu trữ trạng thái

**Vị trí lưu** (đều trong `NEO_VOICE_HOME`, ngoài repo):
- File `license.json`:
  ```json
  {
    "trial": {"first_run":"2026-06-26T08:00:00Z","days":7,"hmac":"<hex>"},
    "license_key": "VM1...."   // null nếu chưa kích hoạt
  }
  ```
- Marker phụ (chống xoá file để trial lại): **Registry** `HKCU\Software\Voice-Master` value `t` = first_run (chuỗi obfuscate base32). Best-effort.

**Toàn vẹn trial (chống sửa tay)**: `hmac = HMAC_SHA256(APP_HMAC_SECRET, first_run + days)`.
`APP_HMAC_SECRET` nhúng trong app (đối xứng → chỉ "tamper-evident" mức cơ bản; .exe khó trích hơn source).

**Tính trạng thái**
```
starts = [file.trial.first_run nếu hmac hợp lệ, registry.t nếu có]
effective_start = min(starts) nếu có; nếu rỗng → tạo trial mới (now), ghi cả 2 nơi
days_left = ceil(7 - (now - effective_start)/1d)
trial_active = days_left > 0
```

---

## 5. State machine & enforcement

```
is_allowed = (NOT enforced) OR trial_active OR licensed_valid

state:
  enforced == false                     → "dev"        (luôn cho phép; repo demo)
  licensed_valid                        → "licensed"   (+exp nếu có)
  not licensed & trial_active           → "trial"      (+days_left)
  not licensed & !trial_active          → "expired"
  license_key tồn tại nhưng verify fail → "invalid"    (kèm reason)
```

**Cờ enforcement**: `VOICE_MASTER_LICENSE_ENFORCED`
- Đọc từ env; mặc định **false**. Bản .exe: electron set env = `true` khi `app.isPackaged` lúc spawn backend (hoặc file `release.flag` trong bundle).

**Điểm chặn (chokepoint duy nhất)**: `routers/tts.create_job()` — dùng chung REST + MCP `synthesize`.
```
if not license_service.is_allowed():
    raise HTTPException(402, detail=make_error("LICENSE_REQUIRED",
        f"Hết hạn dùng thử. Mã máy: {machine_code}").model_dump()
        | {"machine_code": machine_code, "days_left": 0})
```
- MCP `synthesize` đã map HTTPException → JSON → agent nhận `{"error_code":"LICENSE_REQUIRED", ...}`.
- Các thao tác khác (list voices, history, settings, model status) **không chặn**.

---

## 6. API (REST)

### GET `/license/status` → 200
```json
{"state":"trial","enforced":true,"days_left":5,"machine_code":"XXXX-XXXX-XXXX-XXXX",
 "exp":null,"tier":null,"reason":null}
```
### POST `/license/activate`  body `{"key":"VM1...."}`
- 200 hợp lệ: `{"ok":true,"state":"licensed","exp":null,"message":"Kích hoạt thành công"}` (ghi `license_key` vào `license.json`).
- 400 sai: `{"error_code":"LICENSE_INVALID","message":"...","reason":"bad_signature|wrong_machine|expired|format"}`.
### `/health` (mở rộng)
Thêm khối: `"license":{"state":"trial","enforced":true,"days_left":5}`.

**Error code mới** (thêm vào `models/schemas.ERROR_MESSAGES`):
- `LICENSE_REQUIRED` = "Hết hạn dùng thử. Vui lòng kích hoạt bằng mã đăng ký."
- `LICENSE_INVALID` = "Mã đăng ký không hợp lệ hoặc không khớp máy này."

### MCP (tuỳ chọn): tool `get_license_status` (đọc trạng thái) — để agent biết còn bao nhiêu ngày.

---

## 7. Frontend

- **Hook** `src/hooks/useLicense.ts`: `{status, loading, activate(key), refetch}` (poll nhẹ qua `/license/status`).
- **Trang "Bản quyền / Kích hoạt"** `src/components/License.tsx` (thêm mục sidebar 🔑):
  - Badge trạng thái: `Dùng thử — còn N ngày` / `Đã kích hoạt` / `Hết hạn dùng thử`.
  - **Machine Code** + nút Copy.
  - Ô dán License Key + nút **Kích hoạt** → gọi activate → toast thành công/lỗi.
  - Hướng dẫn 1–2 dòng: "Gửi Mã máy cho tác giả (📞 0976202028) để nhận mã đăng ký."
- **Sidebar footer**: badge `Dùng thử: còn N ngày` (ẩn khi licensed/dev).
- **CreateVoice**: khi `state==="expired"` → thay nút Tạo MP3 bằng banner "Hết hạn dùng thử → Kích hoạt"
  dẫn sang trang Bản quyền; đồng thời bắt lỗi `LICENSE_REQUIRED` trả về từ job.
- **types** + **apiClient**: `getLicenseStatus()`, `activateLicense(key)`.

---

## 8. Công cụ tác giả (offline)

- `tools/license_keygen.py` (chạy **một lần**): tạo Ed25519 keypair → `tools/keys/private.pem` (gitignore) +
  in **public key** (raw base64) để dán vào `backend/services/license_core.py` (`PUBLIC_KEY_B64`).
- `tools/license_gen.py`:
  ```
  python tools/license_gen.py --machine-code XXXX-XXXX-XXXX-XXXX [--exp 2027-06-26] [--tier std]
  → in ra License Key "VM1...."
  ```
  Dùng `tools/keys/private.pem`. Báo lỗi nếu thiếu private key.
- `tools/README.md`: HOWTO + cảnh báo **giữ private key bí mật, không commit**.
- `.gitignore`: thêm `tools/keys/`.

---

## 9. Đóng gói .exe

**Cấu hình build**
- `app.isPackaged` (electron) → khi spawn backend, set env `VOICE_MASTER_LICENSE_ENFORCED=true`
  (sửa `electron/main.ts startPythonBackend`: thêm `env: {...process.env, VOICE_MASTER_LICENSE_ENFORCED: '1'}`).

**Backend CPU-only (nhẹ)**
- Bundle riêng (không dùng .venv GPU hiện tại). Thành phần: Python portable (embeddable/relocatable) +
  `vieneu` (minimal, **không torch**) + `onnxruntime` + `fastapi uvicorn pydantic cryptography huggingface_hub
  aiosqlite mcp sse-starlette pydub soundfile`.
- VieNeu v3 Turbo chạy **ONNX/CPU** (đã xác nhận trong `vieneu/factory.py`). Không kèm CUDA/torch.
- `scripts/build_release.ps1`: dựng `python/` runtime CPU-only → đặt cạnh app (electron main tìm `rootDir/python/python.exe`).

**electron-builder**
- `extraResources`: copy `backend/`, `python/`, `scripts/start_backend_detached.ps1` vào bản đóng gói.
- Target: `dir` (portable). Tuỳ chọn `nsis` (setup .exe + icon + shortcut).
- Model VieNeu **không nhúng** → tải lần đầu qua UI/`ensure_model_ready`.

**Layout bản phát hành**
```
Voice-Master/
├─ Voice-Master.exe        # electron
├─ resources/
│   ├─ backend/            # mã backend
│   └─ python/             # python portable CPU-only + deps
└─ (model tải về ~/.cache/huggingface khi chạy lần đầu)
```

---

## 10. Threat model (trung thực)

| Chống được | Không chống được |
|------------|------------------|
| Giả mạo License Key (thiếu private key) | Người sửa **mã nguồn demo** rồi tự build (repo public — chấp nhận) |
| Dùng key máy A cho máy B (ràng buộc machine_code) | Reverse-engineer .exe rồi patch (chỉ tăng rào cản, không tuyệt đối) |
| Sửa tay file trial (HMAC) / xoá file để trial lại (registry marker) | Trải lại bằng cách dọn cả registry + đổi MachineGuid (hiếm, chấp nhận) |

→ Mục tiêu thực tế: **chặn người dùng thường + chống chia sẻ/giả key**, đủ cho mô hình bán bản .exe.

---

## 11. Danh sách file thay đổi

**Backend (mới):** `services/license_core.py`, `services/machine_id.py`, `services/trial.py`,
`services/license_service.py`, `routers/license.py`.
**Backend (sửa):** `config.py` (cờ + APP_SALT/HMAC + đường file), `models/schemas.py` (error codes + schema),
`routers/tts.py` (gate trong create_job), `routers/health.py` (+license summary), `main.py` (đăng ký router),
`mcp_server.py` (tuỳ chọn `get_license_status`).
**Frontend (mới):** `hooks/useLicense.ts`, `components/License.tsx`.
**Frontend (sửa):** `App.tsx` (+screen), `components/Sidebar.tsx` (nav + badge), `components/CreateVoice.tsx`
(gate expired), `lib/apiClient.ts`, `types/index.ts`.
**Tooling:** `tools/license_keygen.py`, `tools/license_gen.py`, `tools/README.md`, `.gitignore` (+`tools/keys/`).
**Đóng gói:** `electron/main.ts` (env enforced khi packaged), `scripts/build_release.ps1`, `package.json` (build/extraResources).
**Docs:** README, huong-dan-su-dung, AGENT_SETUP.

---

## 12. Test plan

**Unit (pytest, mock — TEST keypair monkeypatch `PUBLIC_KEY_B64`)**
- license_core: sign→verify OK; sửa 1 byte payload → fail; sai machine_code → fail; exp quá hạn → fail; sai format/prefix → fail.
- machine_id: ổn định nhiều lần; định dạng `XXXX-XXXX-XXXX-XXXX`; fallback khi không có registry.
- trial: lần đầu = 7 ngày; first_run lùi 8 ngày → expired; xoá file còn registry → vẫn đúng; HMAC sai → coi như mới.
- license_service: dev/trial/licensed/expired/invalid; activate → licensed + lưu key; is_allowed đúng theo cờ.

**Integration**
- Cờ OFF (demo): tạo job không bị chặn.
- Cờ ON, trial active: tạo job OK; trial hết: `create_job` → 402 `LICENSE_REQUIRED`; activate key (TEST) → licensed → tạo job OK.
- MCP: cờ ON + expired → `synthesize` trả JSON `LICENSE_REQUIRED`.

**Manual / build (K5)**
- Bản .exe trên máy không có Python: chạy → tải model → tạo voice; đếm ngày trial; hết hạn chặn; nhập key → mở khoá.

**DoD:** `pytest -q` xanh (không hồi quy); demo chạy không vướng license; .exe enforce đúng; tác giả cấp key cho 1 máy thật thành công, máy khác bị từ chối.

---

## 13. Thứ tự triển khai (sequencing)
```
L1 crypto core ─┐
L2 machine_id ──┼─► L4 license_service ─► L5 endpoints ─► L8 frontend
L3 trial ───────┘                       └─► L6 gate (create_job)
L7 keygen/gen (song song, cần L1)
K1 cờ enforced ─► K2 backend CPU-only ─► K3 electron-builder ─► K4 NSIS(opt) ─► K5 verify
L9 docs · L10 tests/verify (sau cùng)
```
Khuyến nghị làm **L1–L6 + L10 (lõi license, test bằng cờ ON)** trước → có thể nghiệm thu logic ngay trên dev;
rồi **L7–L8** (tooling + UI); cuối cùng **K1–K5** (đóng gói).
