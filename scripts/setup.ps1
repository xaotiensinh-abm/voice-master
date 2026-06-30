# Voice-Master - one-command setup for an agent / new machine.
# Installs uv + ffmpeg (if needed), installs backend deps, starts the backend.
# Default = CPU/ONNX (works everywhere). Add -Gpu to also install CUDA torch
# (NVIDIA GPU only) so VieNeu renders on the GPU.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # CPU/ONNX
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Gpu     # + CUDA torch
param([switch]$Gpu)
$ErrorActionPreference = 'Stop'

$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'

# 1. Ensure uv (Python env manager) is available.
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "uv not found - installing..."
    try { winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements } catch { }
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) { try { pip install uv } catch { } ; $uv = Get-Command uv -ErrorAction SilentlyContinue }
    if (-not $uv) {
        Write-Error "Could not install uv automatically. Install it: https://docs.astral.sh/uv/  then re-run."
        exit 1
    }
}

# 2. Ensure ffmpeg (needed to export MP3).
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "ffmpeg not found - installing (winget)..."
    try { winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements } catch { }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Warning "ffmpeg not installed. MP3 export will fail until you install it (https://ffmpeg.org) and add to PATH."
    }
}

# 3. Install backend dependencies into backend/.venv from uv.lock (CPU/ONNX).
Write-Host "Installing backend dependencies (uv sync)..."
Push-Location $backend
try {
    uv sync
    if ($Gpu) {
        Write-Host "Installing CUDA torch for GPU (large, ~2.5GB)..."
        uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
    }
} finally { Pop-Location }

# 4. Start the backend as a detached background process.
& (Join-Path $PSScriptRoot 'start_backend_detached.ps1')

Write-Host ""
Write-Host "===================================================================="
Write-Host " Setup complete. Backend runs in the background at 127.0.0.1:8757."
Write-Host " Agent connects via MCP (Streamable HTTP): http://127.0.0.1:8757/mcp"
Write-Host " First time: call MCP tool 'ensure_model_ready' to download the model"
Write-Host " (~700MB), then 'synthesize' -> 'wait_for_job' -> 'download_job_audio'."
Write-Host " Engine: CPU/ONNX by default. For NVIDIA GPU, re-run with -Gpu."
Write-Host " Auto-start at logon (optional): scripts\install_autostart.ps1"
Write-Host "===================================================================="
