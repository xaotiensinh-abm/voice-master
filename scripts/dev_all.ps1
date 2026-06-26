# NEO Voice - Start All Dev Servers
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  NEO Voice Local TTS - Development Mode" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Start backend in background
$backendJob = Start-Process powershell -ArgumentList "-File", "$PSScriptRoot\dev_backend.ps1" -PassThru -WindowStyle Normal
Write-Host "Backend started (PID: $($backendJob.Id))" -ForegroundColor Green

# Wait for backend to be ready
Write-Host "Waiting for backend to be ready..." -ForegroundColor Yellow
$maxRetries = 30
$retry = 0
while ($retry -lt $maxRetries) {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8757/health" -Method Get -TimeoutSec 2
        if ($response.status -eq "ok") {
            Write-Host "Backend ready!" -ForegroundColor Green
            break
        }
    } catch {
        Start-Sleep -Seconds 1
        $retry++
    }
}

if ($retry -ge $maxRetries) {
    Write-Host "Warning: Backend may not be ready yet. Starting UI anyway..." -ForegroundColor Yellow
}

# Start UI
Write-Host "Starting UI..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\.."
pnpm dev
