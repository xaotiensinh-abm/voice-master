# Voice-Master - check whether the backend is running.
#   powershell -ExecutionPolicy Bypass -File scripts\status_backend.ps1
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8757/health' -TimeoutSec 3
    Write-Host "OK - Backend running. status=$($r.status) version=$($r.version)"
    Write-Host "  MCP: http://127.0.0.1:8757/mcp"
    exit 0
} catch {
    Write-Host "DOWN - Backend not responding on port 8757."
    Write-Host "  Start: powershell -ExecutionPolicy Bypass -File scripts\start_backend_detached.ps1"
    exit 1
}
