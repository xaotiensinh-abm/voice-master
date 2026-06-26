# NEO Voice Backend Dev Server
Write-Host "Starting NEO Voice Backend..." -ForegroundColor Cyan

$env:NEO_VOICE_HOME = "$env:APPDATA\NEO Voice"
$env:NEO_VOICE_PORT = "8757"

# Create app data directories
$dirs = @("logs", "models", "exports", "temp")
foreach ($d in $dirs) {
    $path = Join-Path $env:NEO_VOICE_HOME $d
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "  Created: $path" -ForegroundColor DarkGray
    }
}

Set-Location "$PSScriptRoot\..\backend"
uv run uvicorn main:app --host 127.0.0.1 --port 8757 --reload
