# Voice-Master - one-command setup for an agent / new machine.
# Installs uv (if needed), installs backend deps, starts the backend in background.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
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

# 2. Install backend dependencies into backend/.venv from uv.lock.
Write-Host "Installing backend dependencies (uv sync)..."
Push-Location $backend
try { uv sync } finally { Pop-Location }

# 3. Start the backend as a detached background process.
& (Join-Path $PSScriptRoot 'start_backend_detached.ps1')

Write-Host ""
Write-Host "===================================================================="
Write-Host " Setup complete. Backend runs in the background at 127.0.0.1:8757."
Write-Host " Agent connects via MCP (Streamable HTTP): http://127.0.0.1:8757/mcp"
Write-Host " First time: call MCP tool 'ensure_model_ready' to download the model"
Write-Host " (~700MB), then 'synthesize' -> 'wait_for_job' -> 'download_job_audio'."
Write-Host " Auto-start at logon (optional): scripts\install_autostart.ps1"
Write-Host "===================================================================="
