param (
    [switch]$Offline = $false
)

Write-Host "Voice-Master: Bắt đầu đóng gói Portable (Win Unpacked)..." -ForegroundColor Cyan

# 1. Build frontend & electron
Write-Host "1. Building Electron & Frontend..." -ForegroundColor Yellow
pnpm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "Lỗi khi build Frontend/Electron!" -ForegroundColor Red
    exit 1
}

$UnpackedDir = "release\win-unpacked"

# 2. Copy backend
Write-Host "2. Đưa Backend vào gói..." -ForegroundColor Yellow
Copy-Item -Path "backend" -Destination "$UnpackedDir\backend" -Recurse -Force
# Xóa các thư mục thừa trong backend
if (Test-Path "$UnpackedDir\backend\.venv") { Remove-Item "$UnpackedDir\backend\.venv" -Recurse -Force }
if (Test-Path "$UnpackedDir\backend\__pycache__") { Remove-Item "$UnpackedDir\backend\__pycache__" -Recurse -Force }
if (Test-Path "$UnpackedDir\backend\.pytest_cache") { Remove-Item "$UnpackedDir\backend\.pytest_cache" -Recurse -Force }

# 3. Tạo file README.txt hướng dẫn
Write-Host "3. Tạo tài liệu hướng dẫn..." -ForegroundColor Yellow
$ReadmeContent = @"
---------------------------------------------------------
VOICE-MASTER PORTABLE BUNDLE
---------------------------------------------------------

Cách chạy trên máy tính khác:
1. Bạn chỉ cần chạy file [Voice-Master.exe] trong thư mục này.
2. Ứng dụng sẽ tự động gọi Backend. Nó yêu cầu máy tính đích phải có phần mềm [uv] được cài đặt để tự động tải Pytorch và các Model AI.
   (Cài uv bằng lệnh: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex")

NẾU BẠN MUỐN CHẠY HOÀN TOÀN OFFLINE (KHÔNG CẦN UV, KHÔNG CẦN MẠNG):
- Hãy tạo một thư mục tên là "python" ngay cạnh file Voice-Master.exe.
- Bỏ bản Python Portable (hoặc copy toàn bộ thư mục .venv/Scripts và .venv/Lib) vào trong đó, sao cho có file "python\python.exe".
- Khi đó Voice-Master.exe sẽ tự ưu tiên gọi "python\python.exe" thay vì dùng uv.
"@
Set-Content -Path "$UnpackedDir\README.txt" -Value $ReadmeContent -Encoding UTF8

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "ĐÓNG GÓI THÀNH CÔNG!" -ForegroundColor Green
Write-Host "Toàn bộ mã nguồn đã được gộp thành Portable App tại:"
Write-Host "--> D:\TQD-Voice\release\win-unpacked"
Write-Host "Bạn có thể nén thư mục này lại thành .zip và gửi sang máy khác."
Write-Host "==========================================================" -ForegroundColor Green
