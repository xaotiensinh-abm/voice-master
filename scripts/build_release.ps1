# Voice-Master - build the distributable .exe (K3). One command.
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1            # portable folder
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Installer # NSIS setup .exe
param([switch]$Installer)
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 1) Portable CPU-only backend runtime (python/, backend/, ffmpeg/)
& (Join-Path $PSScriptRoot 'build_backend_runtime.ps1')
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
Write-Host "Model VieNeu sẽ tải lần đầu khi chạy. License enforced=ON trong bản đóng gói."
