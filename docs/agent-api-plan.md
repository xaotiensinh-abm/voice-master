# Kế hoạch — MCP/API cho Agent tạo voice theo vòng lặp (v2, đã audit)

> Trạng thái: ✅ ĐÃ TRIỂN KHAI (T0–T10). 46 pytest xanh + smoke thật tạo 2 MP3 qua MCP.
> Hợp đồng dùng cho agent: [docs/agent-api.md](agent-api.md).
> Mục tiêu: agent kết nối → tạo voice từ kịch bản → theo dõi tiến độ → tải file khi
> xong → đưa kịch bản tiếp theo → lặp lại.
> v2: cập nhật sau audit đa chiều (xem §11 nhật ký audit).
> ✅ T0 đã verify: MCP SSE (`/mcp/sse`) connect OK, `list_tools` + `call_tool(list_voices)`
> chạy thật trên backend (script `backend/tests/mcp_verify.py`). Nền móng vững → triển khai tiếp.

## 0. Quick-win: REST localhost ĐÃ chạy được vòng lặp hôm nay

Với agent **cùng máy**, vòng lặp đã khả thi ngay bằng REST hiện có, không cần code mới:
`POST /v1/tts/jobs` → poll `GET /v1/tts/jobs/{id}` → khi `completed` thì
`GET /v1/tts/jobs/{id}/audio` (lưu bytes ra file) → lặp với kịch bản kế.
→ Phần việc MỚI của plan này chủ yếu phục vụ **agent MCP-native** (Claude/Cursor…) +
vài tiện ích (audio_url, wait, model-ready) để vòng lặp gọn và tin cậy hơn.

## 1. Vòng lặp agent mục tiêu

```
ensure_model_ready()                # đảm bảo model VieNeu đã tải
for script in scripts:
    job = synthesize(script, voice_id, mode, emotion, speed)   # → job_id
    result = wait_for_job(job_id, timeout)                     # poll tới khi xong
    download_job_audio(job_id, dest_path)                       # lấy file .mp3
    # tiếp tục script kế tiếp
```

## 2. Hiện trạng (đã có)

- **MCP** (`backend/mcp_server.py`, mount SSE `/mcp/sse`): `synthesize`, `list_voices`,
  `get_job_status`, `get_history` — trả **text người-đọc**.
- **REST** (`backend/routers/tts.py`): `POST /v1/tts/jobs`, `GET /v1/tts/jobs/{id}`,
  `GET /v1/tts/jobs/{id}/audio` (FileResponse mp3), `cancel`/`retry`/`delete`, list.
- Backend tự **chunk script dài + ghép** (text_pipeline + job_queue).
- Model VieNeu: `model_manager` + `/models/*` (status/download/progress).

## 3. Khoảng trống cần lấp

| # | Thiếu | Vì sao cần |
|---|-------|-----------|
| G1 | Tải audio qua MCP (bytes/base64 hoặc copy ra path) | Agent remote qua SSE không đọc được `output_path` của server |
| G2 | `wait_for_job` (poll phía server tới khi xong) | Khép vòng lặp, giảm round-trip |
| G3 | Kiểm tra/đảm bảo model sẵn sàng qua MCP | Tránh synth treo khi model chưa tải |
| G4 | Output JSON có cấu trúc + field `mode`, `audio_url` | Agent parse tin cậy thay vì text |

## 4. Thiết kế

**Nguyên tắc:** MCP là giao diện chính cho agent; mọi tool gọi lại logic REST/service
sẵn có (không nhân đôi). Mọi tool trả **một JSON string** trong `TextContent` (kèm
`EmbeddedResource` cho audio khi cần). Lỗi trả JSON `{ "error_code", "message" }`.

### 4.1. Bộ MCP tools (sau khi nâng cấp)

| Tool | Input | Output (JSON) |
|------|-------|---------------|
| `list_voices` | `{}` | `{voices:[{voice_id,display_name,engine,available,styles,emotions}]}` |
| `get_model_status` | `{}` | `{repo_id,downloaded,total_bytes,percent,state}` |
| `ensure_model_ready` | `{wait?:bool=false, timeout_sec?:int=600}` | `{downloaded,state,percent}` — kích hoạt tải nếu chưa có; **mặc định KHÔNG chờ** (agent poll `get_model_status`); chỉ chờ khi `wait=true` (F5) |
| `synthesize` | `{text, voice_id, mode?, emotion?, speed?}` | `{job_id,status}` — bỏ `filename`/`segments_estimate` (F3,F4); số đoạn xem qua `get_job_status` |
| `get_job_status` | `{job_id}` | `{job_id,status,progress,segments_done,segments_total,output_path,audio_url,error}` |
| `wait_for_job` | `{job_id, timeout_sec?=300, poll_sec?=2}` | trạng thái cuối (như get_job_status) hoặc `{error_code:"TIMEOUT"}` |
| `download_job_audio` | `{job_id, dest_path?, include_base64?=false}` | có `dest_path`: `{saved_path,bytes,voice_id,filename}`; không: `{filename,audio_url,bytes,voice_id}` (+`base64` chỉ khi `include_base64=true`, cap ~25MB) (F7) |
| `get_history` | `{limit?=10}` | `{items:[...]}` |
| `cancel_job` *(tùy chọn)* | `{job_id}` | `{status}` — hủy job giữa loop (F13) |

**Lưu ý in-process (F2):** các tool gọi lại `routers.tts.*` (in-process) phải **bắt
`HTTPException`** và map sang `{error_code,message}` — không để propagate ra MCP.
**Catalog error_code:** tái dùng `ERROR_MESSAGES` (UNKNOWN_VOICE, TEXT_EMPTY,
ENGINE_UNAVAILABLE, JOB_NOT_FOUND, MP3_EXPORT_FAILED…) + mới: `MODEL_NOT_READY`,
`TIMEOUT`, `INVALID_DEST_PATH`, `AUDIO_TOO_LARGE`.

### 4.2. REST parity (bổ sung nhỏ)
- Thêm `audio_url` (tuyệt đối) vào `JobStatusResponse` để agent REST tải trực tiếp.
- Giữ nguyên `GET /v1/tts/jobs/{id}/audio` làm nguồn tải chuẩn.
- (Tuỳ chọn) `download_job_audio` với `dest_path` chỉ áp dụng agent **cùng máy**.

### 4.3. Bảo mật (đã chốt: agent CÙNG MÁY / localhost)
- Backend giữ bind `127.0.0.1` (đã vậy) → chỉ agent cùng máy. **Không thêm auth**, không mở bind ngoài.
- `download_job_audio`: **ưu tiên copy file ra `dest_path`** (agent cùng máy đọc trực tiếp).
  Chặn path traversal — chỉ cho ghi vào path tuyệt đối hợp lệ. base64 chỉ là phương án phụ
  (giới hạn ~25 MB) cho tiện, không phải đường chính.

## 5. Task breakdown (kèm deliverable + acceptance + test)

> Mỗi task PHẢI có test tự động (pytest) gọi thẳng `mcp_server.call_tool(...)` với
> adapter được **mock** (theo mẫu `tests/test_tts_jobs.py`) để không cần GPU/model thật.

### T1 — Khung JSON + helper response (nền tảng)
- **Làm:** helper `_ok(data)`/`_err(code,msg)` trả JSON string; chuẩn hoá toàn bộ tool.
- **Deliverable:** `mcp_server.py` refactor + `models/agent_schemas.py` (nếu cần).
- **Acceptance:** mọi tool trả JSON parse được; lỗi có `error_code`.
- **Test:** `test_mcp_contract.py` — `list_tools()` đúng bộ tool; mỗi tool trả JSON hợp lệ.

### T2 — Model readiness tools (G3)
- **Làm:** `get_model_status`, `ensure_model_ready` (gọi `model_manager`).
- **Acceptance:** trả đúng `downloaded/percent/state`; `ensure_model_ready` idempotent, có chế độ chờ.
- **Test:** mock `model_manager` → các nhánh chưa tải / đang tải / xong.

### T3 — `synthesize` nâng cấp (G4)
- **Làm:** thêm `mode`, `filename`; trả JSON `{job_id,status,segments_estimate}`;
  với voice `vieneu:*` mà model chưa tải → trả `{error_code:"MODEL_NOT_READY"}`.
- **Acceptance:** tạo job hợp lệ trả job_id; voice sai → `UNKNOWN_VOICE`; text rỗng → `TEXT_EMPTY`.
- **Test:** mock adapter + get_db; assert job_id và các nhánh lỗi.

### T4 — `get_job_status` JSON + `audio_url` (G4)
- **Làm:** trả JSON đầy đủ; thêm `audio_url` khi completed.
- **Acceptance:** khớp dữ liệu REST; completed có `audio_url`, failed có `error`.
- **Test:** fake DB nhiều trạng thái (queued/running/completed/failed).

### T5 — `wait_for_job` (G2)
- **Làm:** poll DB tới khi terminal hoặc hết `timeout_sec` (async sleep `poll_sec`).
- **Acceptance:** trả trạng thái cuối khi xong; quá hạn → `{error_code:"TIMEOUT"}`; không chặn event loop.
- **Test:** fake DB chuyển running→completed sau N lần fetch; ca timeout.

### T6 — `download_job_audio` (G1)
- **Làm:** job completed → nếu `dest_path` hợp lệ: copy file, trả `{saved_path,bytes}`;
  nếu không: đọc file, trả `{filename,audio_url,base64,bytes}` (giới hạn kích thước).
- **Acceptance:** job chưa xong → lỗi; file không tồn tại → `MP3_EXPORT_FAILED`;
  `dest_path` ngoài vùng cho phép → từ chối.
- **Test:** tạo file mp3 giả trong temp; assert copy/base64; ca lỗi.

### T7 — REST parity
- **Làm:** thêm `audio_url` vào `JobStatusResponse` (build từ host/port + job_id).
- **Acceptance:** `GET /v1/tts/jobs/{id}` completed có `audio_url` tải được.
- **Test:** TestClient: tạo (mock) → status có audio_url đúng định dạng.

### T8 — Contract doc cho agent
- **Làm:** `docs/agent-api.md` — base URL, cách kết nối MCP SSE, bảng tool I/O,
  bảng error_code, ví dụ vòng lặp đầy đủ (mock + thật), lưu ý bảo mật localhost.
- **Acceptance:** theo doc, một agent chạy được full loop trên máy local.

### T9 — Integration test full-loop + smoke thủ công
- **Làm:** `tests/test_mcp_agent_flow.py` — chạy chuỗi
  `ensure_model_ready(mock)→synthesize→wait_for_job→download_job_audio` với adapter giả
  (tạo file wav/mp3 nhanh) + DB sqlite tạm; + script smoke `scripts/agent_smoke.py`
  gọi MCP/REST thật khi backend chạy.
- **Acceptance:** test xanh end-to-end không cần GPU; smoke tạo được 2 file liên tiếp (loop).

## 6. Chiến lược kiểm thử (tổng) — đã siết theo audit F9/F10
- **T1–T6 unit/contract (mock hoàn toàn):** pytest gọi `call_tool` trực tiếp; mock
  `get_adapter` + `model_manager`; fake DB hoặc sqlite tạm. **Không worker, không ffmpeg, không GPU.**
- **T9 integration full-loop:** đăng ký **fake adapter** (`register_adapter("vieneu", Fake)`)
  ghi wav nhỏ tức thì; **mock các hàm export audio** (`join_wav_segments`,
  `normalize_loudness`, `export_mp3`) ghi mp3 giả → **không cần ffmpeg/thư viện audio**;
  `start_worker()` + sqlite tạm; chạy chuỗi `synthesize→wait_for_job→download_job_audio`.
- **Smoke thật (thủ công):** `scripts/agent_smoke.py` khi backend `127.0.0.1:8757` sống:
  list_voices → ensure_model_ready → synth 2 kịch bản nối tiếp → tải 2 mp3 → assert >1KB.
- **Lệnh:** `pytest -q` (toàn bộ xanh, không hồi quy 25 test hiện có).

## 7b. Non-goals (chặn scope creep)
- KHÔNG remote / mở bind ngoài localhost, KHÔNG auth token (agent cùng máy).
- KHÔNG `synthesize_batch` (agent lặp tuần tự).
- KHÔNG voice cloning / chọn backbone.
- KHÔNG đổi cơ chế chunk/worker hiện có (tái dùng nguyên trạng).

## 9. Rủi ro & giảm thiểu
| Rủi ro | Giảm thiểu |
|--------|-----------|
| Mount MCP SSE hiện tại có thể chưa chạy | **T0 verify trước** mọi việc |
| `create_job` raise HTTPException làm vỡ MCP | Bắt & map JSON trong từng tool (T1/T3) |
| Test phụ thuộc ffmpeg/GPU | Mock export + fake adapter (T9) |
| `wait_for_job`/`ensure_model_ready` chặn tool-call lâu | timeout mặc định; `ensure_model_ready wait=false` mặc định |
| base64 phình context | opt-in; ưu tiên `dest_path` |
| Job xếp hàng → wait lâu | Doc nêu rõ worker tuần tự |

## 11. Nhật ký audit (đa chiều)
F1→T0 mới; F2→bắt HTTPException; F3→bỏ `filename`; F4→bỏ `segments_estimate`;
F5→`ensure_model_ready wait=false`; F7→base64 opt-in; F8→guard path gọn; F9/F10→test mock
export + tách unit/integration; F11→§0 quick-win REST; F12→§7b non-goals + §9 risks;
F13→`cancel_job` optional.

## 7. Tiêu chí hoàn thành (Definition of Done)
- Agent qua MCP local làm trọn vòng lặp: liệt kê giọng → đảm bảo model → tạo từ kịch bản
  → theo dõi %→ tải .mp3 (path hoặc bytes) → lặp với kịch bản mới.
- Mọi tool trả JSON có cấu trúc + error_code rõ ràng.
- T1–T7 có test tự động; T9 integration full-loop xanh; doc T8 đủ để agent tự dùng.
- `pytest -q` xanh; không phá vỡ REST/MCP hiện có.

## 8. Quyết định đã chốt
- **Agent cùng máy (localhost)** → giữ bind 127.0.0.1, không auth; `download_job_audio` lấy
  `dest_path` làm đường chính (copy file), base64/URL là phụ.
- **Không làm `synthesize_batch`** → agent tự lặp tuần tự (worker vốn chạy tuần tự).
- `download_job_audio` trả kèm metadata cơ bản (voice_id, segments, output filename) trong response.
