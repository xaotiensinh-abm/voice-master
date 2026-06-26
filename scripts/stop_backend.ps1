# Voice-Master - stop the background backend (whatever is listening on 8757).
#   powershell -ExecutionPolicy Bypass -File scripts\stop_backend.ps1
$ErrorActionPreference = 'SilentlyContinue'

$conns = Get-NetTCPConnection -LocalPort 8757 -State Listen -ErrorAction SilentlyContinue
if (-not $conns) {
    Write-Host "Backend is not running (port 8757 is free)."
    exit 0
}

$pids = $conns.OwningProcess | Select-Object -Unique
foreach ($processId in $pids) {
    $parent = (Get-CimInstance Win32_Process -Filter "ProcessId=$processId").ParentProcessId
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    if ($parent) {
        $pname = (Get-CimInstance Win32_Process -Filter "ProcessId=$parent").Name
        if ($pname -eq 'python.exe') { Stop-Process -Id $parent -Force -ErrorAction SilentlyContinue }
    }
    Write-Host "Stopped backend (PID $processId)."
}
