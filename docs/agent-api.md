# Voice-Master — Agent API (MCP + REST)

Hợp đồng để một agent tự động: **liệt kê giọng → đảm bảo model → tạo voice từ kịch
bản → theo dõi tiến độ → tải file → lặp lại**.

- **Base URL:** `http://127.0.0.1:8757` (backend chỉ bind localhost — agent phải chạy **cùng máy**, không auth).
- **MCP — KHUYẾN NGHỊ: Streamable HTTP** tại `http://127.0.0.1:8757/mcp` (transport hiện đại, đa số agent dùng mặc định).
- **MCP — Legacy SSE** (chỉ dùng nếu client cũ): `GET /mcp/sse` + `POST /mcp/messages`. Nếu gặp `httpx.ReadError` khi dùng SSE, hãy chuyển sang Streamable HTTP `/mcp`.
- **Worker tuần tự:** mỗi lần chỉ chạy 1 job; job mới xếp hàng. `wait_for_job` có thể lâu nếu có job trước.
- **Script dài:** backend tự chia đoạn (≤900 ký tự/đoạn cho VieNeu) rồi ghép lại thành 1 MP3.

## 1. Kết nối MCP (Python) — Streamable HTTP (khuyến nghị)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://127.0.0.1:8757/mcp") as (read, write, *_):
    async with ClientSession(read, write) as session:
        await session.initialize()
        res = await session.call_tool("list_voices", {})
        # res.content[0].text là JSON string
```

Legacy SSE (nếu cần): `from mcp.client.sse import sse_client` →
`sse_client("http://127.0.0.1:8757/mcp/sse")`.

Mọi tool trả **một JSON string** trong `TextContent`. Lỗi có dạng
`{"error_code": "...", "message": "..."}`.

## 2. Bộ tool MCP

| Tool | Input | Output (JSON) |
|------|-------|---------------|
| `list_voices` | `{}` | `{voices:[{voice_id,display_name,engine,available,styles,emotions}]}` |
| `get_model_status` | `{}` | `{repo_id,downloaded,total_bytes,cache_path,state,percent,error}` |
| `ensure_model_ready` | `{wait?=false,timeout_sec?=600}` | `{downloaded,state,percent,error}` |
| `synthesize` | `{text,voice_id,mode?=neutral,emotion?=neutral,speed?=1.0}` | `{job_id,status}` |
| `get_job_status` | `{job_id}` | `{job_id,status,progress,segments_done,segments_total,output_path,audio_url,error}` |
| `wait_for_job` | `{job_id,timeout_sec?=300,poll_sec?=2}` | status cuối, hoặc `{error_code:"TIMEOUT",...}` |
| `download_job_audio` | `{job_id,dest_path?,include_base64?=false}` | có `dest_path`: `{saved_path,bytes,voice_id,filename}`; không: `{filename,audio_url,bytes,voice_id(,base64)}` |
| `get_history` | `{limit?=10}` | `{items:[{job_id,voice_id,display_name,text_preview,output_path,audio_url,created_at}]}` |
| `cancel_job` | `{job_id}` | `{status}` |

- `mode`: `neutral|news|story|podcast`. `emotion`: `neutral|warm|serious|storytelling|excited|sad`.
- Cảm xúc inline (VieNeu, thử nghiệm): chèn thẳng trong `text`: `[cười]`, `[thở dài]`, `[hắng giọng]`.
- `dest_path` phải **tuyệt đối** (file hoặc thư mục). Là thư mục → lưu theo tên gốc.
- `include_base64` chỉ dùng khi cần nhúng (giới hạn 25MB) — localhost nên ưu tiên `dest_path`/`audio_url`.

## 2b. Thêm cảm xúc vào script (để agent tự viết)

Có **3 lớp** điều khiển cảm xúc, dùng kết hợp được. Tất cả truyền qua tool `synthesize`.

### (1) Thẻ cảm xúc inline trong `text` — biểu cảm mạnh nhất (VieNeu, thử nghiệm)
Chèn thẻ **ngay trước** cụm/câu cần biểu cảm. Thẻ được nhúng thẳng vào chuỗi `text`:

| Thẻ | Hiệu ứng |
|-----|----------|
| `[cười]` | cười / vui vẻ |
| `[thở dài]` | thở dài / mệt mỏi, hụt hơi |
| `[hắng giọng]` | hắng giọng, lấy hơi |

Ví dụ: `"[cười] Trời ơi, tin này tuyệt quá! ... [thở dài] Nhưng vẫn còn nhiều việc phải làm."`

Lưu ý: chỉ áp dụng giọng `vieneu:*` (ElevenLabs bỏ qua); là tính năng thử nghiệm nên
**đặt thưa**, mỗi cụm 1 thẻ, ở đầu câu/cụm — lạm dụng sẽ phản tác dụng.

### (2) Tham số `emotion` — ngữ điệu/tốc độ tổng thể của cả job
`neutral` | `warm` (ấm áp) | `serious` (nghiêm túc, chậm hơn) | `storytelling` (kể chuyện, chậm hơn) |
`excited` (hào hứng) | `sad` (trầm buồn, chậm hơn). Áp cho **toàn bộ** đoạn text.

### (3) Tham số `mode` — phong cách đọc
`neutral` | `news` (nhanh, dứt khoát) | `story` (chậm, truyền cảm) | `podcast` (trò chuyện).
Có thể tinh chỉnh thêm `speed` (0.5–2.0).

### Mẹo để agent soạn script có cảm xúc
- Tách ý theo câu/đoạn; chèn thẻ inline ở đúng chỗ **đổi cảm xúc**.
- Khớp `mode`+`emotion` với nội dung: truyện → `mode=story, emotion=storytelling`;
  tin tức → `mode=news, emotion=serious`; quảng cáo vui → `mode=podcast, emotion=excited`.
- Dùng dấu câu để ngắt nhịp (`.`, `!`, `?`, `...`). Hai dòng trống `\n\n` = ngắt đoạn
  (cũng là ranh giới hệ thống tự chia đoạn khi script dài rồi ghép lại).
- Giữ thẻ inline ở dạng đúng chính tả tiếng Việt như bảng trên (có dấu).

### Ví dụ `synthesize` có cảm xúc
```json
{
  "text": "[cười] Chào cả nhà, rất vui được gặp lại! Hôm nay trời thật đẹp.\n\n[thở dài] Nhưng mình vẫn phải bắt tay vào công việc thôi.",
  "voice_id": "vieneu:ngoc_lan",
  "mode": "story",
  "emotion": "warm",
  "speed": 1.0
}
```

## 3. error_code

| Code | Ý nghĩa |
|------|---------|
| `UNKNOWN_VOICE` | voice_id không hợp lệ |
| `TEXT_EMPTY` | text rỗng |
| `MODEL_NOT_READY` | model VieNeu chưa tải — gọi `ensure_model_ready` |
| `ENGINE_UNAVAILABLE` | engine chưa sẵn sàng |
| `JOB_NOT_FOUND` / `JOB_NOT_COMPLETED` | job không tồn tại / chưa xong |
| `MP3_EXPORT_FAILED` | không thấy file output |
| `INVALID_DEST_PATH` | dest_path không tuyệt đối/không tạo được |
| `AUDIO_TOO_LARGE` | file > 25MB khi xin base64 |
| `TIMEOUT` | `wait_for_job` hết giờ |
| `INVALID_REQUEST` / `WORKER_CRASHED` / `UNKNOWN_TOOL` | tham số sai / lỗi nội bộ / sai tên tool |

## 4. Vòng lặp đầy đủ (MCP)

```python
async def call(session, tool, args):
    res = await session.call_tool(tool, args)
    return json.loads(res.content[0].text)

voice_id = (await call(session, "list_voices", {}))["voices"][0]["voice_id"]
await call(session, "ensure_model_ready", {})          # tải nếu cần (poll get_model_status nếu wait=false)

for script in scripts:
    created = await call(session, "synthesize", {"text": script, "voice_id": voice_id, "mode": "story"})
    if "error_code" in created: ...                    # vd MODEL_NOT_READY
    job_id = created["job_id"]
    final = await call(session, "wait_for_job", {"job_id": job_id, "timeout_sec": 240})
    if final["status"] != "completed": ...
    out = await call(session, "download_job_audio",
                     {"job_id": job_id, "dest_path": r"C:\\out\\%s.mp3" % job_id})
    # out["saved_path"] = file MP3 đã lưu → tiếp tục script kế
```

Mẫu chạy thật: [`backend/scripts/agent_smoke.py`](../backend/scripts/agent_smoke.py)
(đã verify: tạo 2 MP3 nối tiếp qua MCP). Verify nền móng: [`backend/tests/mcp_verify.py`](../backend/tests/mcp_verify.py).

## 5. REST (đường nhanh, không cần MCP)

Vòng lặp tương đương bằng REST thuần:
```
POST /v1/tts/jobs            {input:{type:"text",text},voice_id,mode,emotion,speed,output:{format:"mp3"}}  → {job_id}
GET  /v1/tts/jobs/{job_id}   → {status,progress,...,audio_url}   (poll tới completed)
GET  /v1/tts/jobs/{job_id}/audio  → bytes MP3 (lưu ra file)
```
Model VieNeu: `GET /models/status`, `POST /models/download`, `GET /models/download/progress`.

## 6. Bảo mật
- Backend **chỉ localhost**, không auth → chỉ dùng cho agent cùng máy. Không mở bind ngoài.
- `download_job_audio` chỉ ghi vào path tuyệt đối hợp lệ; không nhận path tương đối.
