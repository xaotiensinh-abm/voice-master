# Hướng dẫn sử dụng Voice-Master (giao diện desktop)

Dành cho người dùng thường thao tác trên giao diện. Agent xem [AGENT_SETUP.md](../AGENT_SETUP.md).

## 1. Khởi động
1. Bật backend (chạy ngầm):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\start_backend_detached.ps1
   ```
2. Mở giao diện:
   - Web: `pnpm dev:web` → mở `http://localhost:5173`
   - Hoặc app Electron: `pnpm dev`
3. Góc dưới trái sidebar có chấm trạng thái: **xanh = đã kết nối backend**.

## 2. Tải mô hình lần đầu
Lần đầu dùng giọng VieNeu, app hiện màn **"Cần tải mô hình VieNeu (~700MB)"**:
bấm **Tải mô hình**, đợi thanh tiến độ đầy. Tải một lần, sau đó dùng offline.
Có thể tải/tải lại/xoá trong **Cài đặt → Mô hình**.

## 3. Tạo giọng nói
Vào **Tạo giọng nói**:
1. **Chọn giọng** ở ô sổ xuống (lọc theo engine nếu cần), bấm **Nghe thử**.
2. **Nhập văn bản** (hoặc tab **Chọn file** với `.txt`/`.md`). Văn bản dài sẽ thấy
   badge "🧩 ~N đoạn (tự động ghép)" — hệ thống tự chia đoạn rồi ghép thành 1 MP3.
3. **Tuỳ chỉnh**: Phong cách đọc (mode), Cảm xúc (emotion), Tốc độ.
4. Bấm **🎙 Tạo MP3** → xem tiến độ → khi xong: nghe trực tiếp, **Tải MP3**, hoặc **Mở thư mục**.

## 4. Thêm cảm xúc vào giọng đọc
Ba lớp kết hợp được:
- **Thẻ inline trong văn bản** (mạnh nhất, chỉ giọng VieNeu, thử nghiệm): bấm nút
  **Chèn cảm xúc** (`[cười]`, `[thở dài]`, `[hắng giọng]`) — thẻ chèn vào vị trí con trỏ.
  Đặt thẻ ngay trước cụm cần biểu cảm, dùng thưa.
- **Cảm xúc (emotion)**: trung tính / ấm áp / nghiêm túc / kể chuyện / hào hứng / trầm buồn.
- **Phong cách (mode)** + **Tốc độ**: tin tức / đọc truyện / podcast…

Mở **❔ Hướng dẫn cảm xúc** ngay dưới ô văn bản để xem ví dụ.

## 5. Kết nối Agent / API
Vào trang **🔌 Kết nối Agent / API**: xem & copy endpoint (MCP `http://127.0.0.1:8757/mcp`,
REST base), cấu hình MCP để dán vào client (Claude/Cursor), danh sách tool, ví dụ vòng lặp,
và hướng dẫn chèn cảm xúc cho agent.

## 6. Cài đặt
- **Mô hình**: trạng thái/dung lượng/đường dẫn cache, tải lại, xoá.
- **ElevenLabs** (tuỳ chọn): nhập API key để dùng giọng cloud (gửi văn bản lên máy chủ ElevenLabs).
- **Chung**: thư mục đầu ra, bitrate MP3, engine mặc định.

## 7. Xử lý sự cố
| Hiện tượng | Cách xử lý |
|-----------|-----------|
| Sidebar báo "Mất kết nối backend" / `localhost:5173` không vào | Backend chưa chạy → `scripts\start_backend_detached.ps1`; kiểm tra `scripts\status_backend.ps1` |
| Dropdown giọng trống | Reload trang (F5); backend vừa khởi động lại sẽ tự nạp lại danh sách |
| Bấm Tạo MP3 không được | Chưa chọn giọng / chưa nhập text / model VieNeu chưa tải xong |
| Tạo thất bại | Xem thông báo lỗi; với VieNeu kiểm tra mô hình đã tải (Cài đặt → Mô hình) |

## 8. Tắt backend
```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_backend.ps1
```
