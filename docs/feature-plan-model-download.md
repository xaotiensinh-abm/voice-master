# Kế hoạch phát triển — Tải mô hình lần đầu + Tối ưu code

> Trạng thái: ✅ ĐÃ TRIỂN KHAI (tasks #5–#9). Mặc định mô hình: **VieNeu-TTS v3 Turbo**.
> Nguồn tham khảo: https://github.com/pnnbao97/VieNeu-TTS
>
> Files: backend `services/model_manager.py`, `routers/models.py`, `/health` (+`model_downloaded`,
> `max_chars_per_chunk`); frontend `hooks/useModelStatus.ts`, `components/ModelDownloadGate.tsx`,
> Settings → mục Mô hình; `CreateVoice` tách thành `components/create/{VoicePicker,EmotionGuide,JobResult}.tsx`.

## 1. Bối cảnh & mục tiêu

**Vấn đề người dùng nêu:** Người dùng lần đầu phải tải mô hình VieNeu-TTS về máy
thay vì đóng gói sẵn trong bộ cài (rất nặng).

**Hiện trạng (đã xác minh trong repo):**
- SDK `vieneu` **tự tải mô hình từ HuggingFace ngay lần gọi `Vieneu()` đầu tiên**,
  cache tại `~/.cache/huggingface`. Repo mô hình: `pnnbao-ump/VieNeu-TTS-v3-Turbo`.
- Bộ cài hiện tại (`package.json` → `build.files`) **chỉ đóng gói** `dist/` +
  `dist-electron/`, **không** kèm mô hình. → Mục tiêu "không bundle" **đã đạt**.
- Khoảng trống thực sự là **UX**: việc tải đang diễn ra ngầm bên trong lần
  `synthesize` đầu tiên ([backend/adapters/vieneu_adapter.py:166-171](../backend/adapters/vieneu_adapter.py)),
  nên người dùng lần đầu chỉ thấy app "treo" rất lâu, không có % tiến độ, không
  cảnh báo dung lượng.

**Mục tiêu của kế hoạch:**
1. Phát hiện mô hình đã tải hay chưa khi khởi động.
2. Màn/modal tải lần đầu: cảnh báo dung lượng + thanh tiến độ + xử lý lỗi.
3. Quản lý mô hình trong Settings (xem trạng thái, tải lại, xoá, vị trí cache).
4. Gộp các tối ưu từ /code-review.

## 2. Tính năng A — Tải mô hình lần đầu (Turbo)

### 2.1. Backend (FastAPI)

Tạo router mới `backend/routers/models.py` + service `backend/services/model_manager.py`.

Dùng `huggingface_hub`:
- **Kiểm tra đã tải:** `snapshot_download(repo_id, local_files_only=True)` trong
  try/except → có đường dẫn = đã tải; lỗi = chưa tải. (Hoặc `scan_cache_dir()`.)
- **Ước tính dung lượng:** `HfApi().model_info(repo_id, files_metadata=True)` rồi
  cộng `file.lfs.size` (fallback `file.size`).
- **Tải có tiến độ:** chạy `snapshot_download` trong thread nền; theo dõi % bằng
  cách poll tổng dung lượng thư mục cache tạm (`*.incomplete`) so với
  `total_bytes`. HF tự hỗ trợ **resume** khi tải lại.

Endpoints (theo mẫu polling 1.5s đã có ở [useJobs.ts](../src/hooks/useJobs.ts)):
- `GET  /models/status` → `{ engine, repo_id, downloaded: bool, total_bytes, cache_path }`
- `POST /models/download` → bắt đầu tải nền (idempotent; có lock chống tải trùng) → `{ state: "downloading" }`
- `GET  /models/download/progress` → `{ state: idle|downloading|done|error, downloaded_bytes, total_bytes, percent, error? }`
- `DELETE /models/{repo_id}` (tuỳ chọn) → xoá khỏi cache (`scan_cache_dir().delete_revisions`).

Mở rộng `EngineHealth`/`/health`: thêm cờ `model_downloaded` cho VieNeu để frontend
phân biệt 3 trạng thái: *SDK chưa cài* / *đã cài nhưng chưa tải mô hình* / *sẵn sàng*.

### 2.2. Frontend (React)

- Hook `useModelStatus.ts`: gọi `/models/status`, expose `downloaded`, `progress`,
  `startDownload()`, polling khi đang tải.
- **Cổng chặn lần đầu (first-run gate):** khi chọn giọng VieNeu mà mô hình chưa tải,
  thay khu vực nhập liệu bằng card "Cần tải mô hình VieNeu (~X GB)" + nút **Tải mô hình**
  + thanh tiến độ + trạng thái. Sau khi xong → mở khoá tạo voice.
- **Settings → mục "Mô hình":** trạng thái (đã tải/chưa), dung lượng, vị trí cache,
  nút Tải lại / Xoá.
- Vô hiệu hoá nút "🎙 Tạo MP3" kèm tooltip rõ ràng khi chưa có mô hình (thay vì để
  treo trong lần synthesize đầu).

### 2.3. Edge cases cần xử lý
- Offline / mất mạng giữa chừng → báo lỗi, cho **thử lại** (HF resume). Không có nút huỷ.
- Thiếu dung lượng đĩa → kiểm tra trước, cảnh báo.
- Tải trùng (2 lần bấm / 2 cửa sổ) → lock ở backend.
- CPU vs GPU: Turbo auto chuyển PyTorch engine khi có CUDA — không đổi mô hình tải.

## 3. Tối ưu từ /code-review (gộp vào)

| # | Việc | File |
|---|------|------|
| 1 | ✅ Đã sửa: reset `selectedVoiceId` khi bộ lọc engine loại giọng đang chọn | [CreateVoice.tsx](../src/components/CreateVoice.tsx) |
| 2 | Tách `CreateVoice.tsx` (~600 dòng) → `VoicePicker`, `EmotionGuide`, `JobResult` (quy tắc >200 dòng trong CLAUDE.md) | src/components/create/ |
| 3 | Một nguồn sự thật cho giới hạn chunk: thêm vào `/health` hoặc `/meta` (`max_chars_per_chunk`) để frontend không hardcode lệch backend | backend/config.py → health, useHealth.ts |
| 4 | `estimateSegments` chạy regex split mỗi lần gõ — chấp nhận được nhưng có thể đơn giản hoá cho text rất dài | CreateVoice.tsx |

## 4. Quyết định đã chốt (phạm vi)
- **Chỉ dùng Turbo** (`pnnbao-ump/VieNeu-TTS-v3-Turbo`). KHÔNG làm chọn backbone
  (v2/0.3B) → bỏ `DELETE /models/{repo_id}` động theo repo, chỉ cần thao tác trên
  một repo Turbo cố định.
- **Không huỷ tải** giữa chừng — chỉ tải tới khi xong hoặc lỗi (cho thử lại/resume).
- **Không cho đổi thư mục cache** HuggingFace — dùng mặc định `~/.cache/huggingface`.

## 5. Roadmap mở rộng (tuỳ chọn, ngoài phạm vi đợt này)
- **Nhân bản giọng (voice cloning)** từ audio mẫu — VieNeu hỗ trợ; tính năng lớn.
- **Map cảm xúc → tự chèn thẻ:** nối dropdown "Cảm xúc" với việc tự chèn
  `[cười]`/`[thở dài]`...
