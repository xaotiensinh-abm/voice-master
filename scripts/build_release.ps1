# Voice-Master - build the distributable .exe (K3). One command.
# GPU build by default (torch CUDA). Use -Cpu for an ONNX/CPU-only build.
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1             # GPU portable
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Cpu        # CPU portable
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Installer  # GPU NSIS setup
param([switch]$Cpu, [switch]$Installer)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 1) Portable backend runtime (python/, backend/, ffmpeg/)
if ($Cpu) {
    & (Join-Path $PSScriptRoot 'build_backend_runtime.ps1') -Cpu
} else {
    & (Join-Path $PSScriptRoot 'build_backend_runtime.ps1')
}
if ($LASTEXITCODE -ne 0) { Write-Error "Backend runtime build failed."; exit 1 }

# 2) Node deps
if (-not (Test-Path (Join-Path $root 'node_modules'))) {
    Write-Host "Installing node dependencies (pnpm install)..."
    pnpm install
}

# 3) Frontend + electron-builder
if ($Installer) {
    Write-Host "Building NSIS installer..."
    pnpm run build:installer
} else {
    Write-Host "Building portable app..."
    pnpm run build
}

Write-Host ""
Write-Host "OK - output in: $(Join-Path $root 'release')"
Write-Host "Portable app: release\win-unpacked\Voice-Master.exe (kèm python\, backend\, ffmpeg\ bên cạnh)."
Write-Host "Khách mở app -> bấm nút Tải mô hình (lần đầu, ~700MB) -> tạo voice. License enforced=ON."
