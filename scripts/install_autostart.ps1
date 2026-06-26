# Voice-Master - auto-start the backend at Windows logon (NO admin needed).
# Drops a hidden launcher in the current user's Startup folder.
# Install:  powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
# Remove :  powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Remove
param([switch]$Remove)
$ErrorActionPreference = 'Stop'

$startScript = Join-Path $PSScriptRoot 'start_backend_detached.ps1'
$startup = [Environment]::GetFolderPath('Startup')
$vbs = Join-Path $startup 'VoiceMasterBackend.vbs'

if ($Remove) {
    if (Test-Path $vbs) { Remove-Item $vbs -Force; Write-Host "Removed autostart: $vbs" }
    else { Write-Host "No autostart launcher found." }
    return
}

if (-not (Test-Path $startScript)) { Write-Error "Not found: $startScript"; exit 1 }

# VBS launches PowerShell hidden (no console flash). Inner path quotes are doubled per VBS rules.
$inner = 'powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""' + $startScript + '""'
$line1 = 'Set sh = CreateObject("WScript.Shell")'
$line2 = 'sh.Run "' + $inner + '", 0, False'
Set-Content -Path $vbs -Value $line1, $line2 -Encoding ASCII

Write-Host "OK - Installed autostart launcher (runs at logon, hidden, no admin):"
Write-Host "  $vbs"
Write-Host "  Remove: powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Remove"
