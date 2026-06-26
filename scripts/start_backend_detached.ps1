# Voice-Master - start the backend as a DETACHED background process.
# Keeps running after this terminal (or an agent session) closes.
#   powershell -ExecutionPolicy Bypass -File scripts\start_backend_detached.ps1
$ErrorActionPreference = 'Stop'

$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$py      = Join-Path $backend '.venv\Scripts\python.exe'

if (-not (Test-Path $py)) {
    Write-Error "Python venv not found. Run first:  cd `"$backend`"; uv sync"
    exit 1
}

$existing = Get-NetTCPConnection -LocalPort 8757 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Backend already running (PID $($existing.OwningProcess)) at http://127.0.0.1:8757"
    exit 0
}

$logDir = Join-Path $backend 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$out = Join-Path $logDir 'backend.out.log'
$err = Join-Path $logDir 'backend.err.log'

$env:NEO_VOICE_PORT = '8757'
$proc = Start-Process -FilePath $py -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','8757' -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
Write-Host "Started backend in background (PID $($proc.Id)). Waiting for readiness..."

$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8757/health' -TimeoutSec 2 } catch { $r = $null }
    if ($r -and $r.status -eq 'ok') { $ok = $true; break }
}

if ($ok) {
    Write-Host "OK - Backend ready."
    Write-Host "  REST: http://127.0.0.1:8757"
    Write-Host "  MCP : http://127.0.0.1:8757/mcp  (Streamable HTTP)"
    exit 0
}
Write-Warning "Backend did not respond within 30s. See log: $err"
exit 1
