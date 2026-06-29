# Voice-Master - assemble a portable CPU-only backend runtime for packaging (K2).
# Produces release-staging/{python, backend, ffmpeg} consumed by electron-builder
# extraFiles. NO torch (VieNeu v3 Turbo runs on CPU via ONNX Runtime).
#   powershell -ExecutionPolicy Bypass -File scripts\build_backend_runtime.ps1
$ErrorActionPreference = 'Stop'

$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$staging = Join-Path $root 'release-staging'
$pyDir   = Join-Path $staging 'python'
$ffDir   = Join-Path $staging 'ffmpeg'

$PY_VER       = '3.12.7'
$PY_EMBED_URL = "https://www.python.org/ftp/python/$PY_VER/python-$PY_VER-embed-amd64.zip"
$GETPIP_URL   = 'https://bootstrap.pypa.io/get-pip.py'
$FFMPEG_URL   = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'

New-Item -ItemType Directory -Force -Path $staging | Out-Null
$tmp = Join-Path $staging '_dl'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# 1) Portable (embeddable) Python -----------------------------------------
if (-not (Test-Path (Join-Path $pyDir 'python.exe'))) {
    Write-Host "Downloading embeddable Python $PY_VER..."
    $zip = Join-Path $tmp 'python-embed.zip'
    Invoke-WebRequest -Uri $PY_EMBED_URL -OutFile $zip
    New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
    Expand-Archive -Path $zip -DestinationPath $pyDir -Force

    # Enable site-packages so pip works (uncomment 'import site' in *._pth).
    $pth = Get-ChildItem $pyDir -Filter 'python*._pth' | Select-Object -First 1
    (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName -Encoding ascii

    Write-Host "Installing pip..."
    $getpip = Join-Path $tmp 'get-pip.py'
    Invoke-WebRequest -Uri $GETPIP_URL -OutFile $getpip
    & (Join-Path $pyDir 'python.exe') $getpip --no-warn-script-location
}

# 2) CPU-only dependencies -------------------------------------------------
Write-Host "Installing backend dependencies (CPU-only, no torch)..."
& (Join-Path $pyDir 'python.exe') -m pip install --no-warn-script-location -r (Join-Path $backend 'requirements-cpu.txt')

# 3) ffmpeg ---------------------------------------------------------------
if (-not (Test-Path (Join-Path $ffDir 'ffmpeg.exe'))) {
    Write-Host "Downloading ffmpeg..."
    $ffzip = Join-Path $tmp 'ffmpeg.zip'
    Invoke-WebRequest -Uri $FFMPEG_URL -OutFile $ffzip
    $ffx = Join-Path $tmp 'ffmpeg_x'
    Expand-Archive -Path $ffzip -DestinationPath $ffx -Force
    $exe = Get-ChildItem $ffx -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1
    New-Item -ItemType Directory -Force -Path $ffDir | Out-Null
    Copy-Item $exe.FullName (Join-Path $ffDir 'ffmpeg.exe') -Force
}

# 4) Clean backend source copy --------------------------------------------
Write-Host "Copying backend source (excluding venv/cache/tests)..."
$dstBackend = Join-Path $staging 'backend'
robocopy $backend $dstBackend /E /NFL /NDL /NJH /NJS /NP `
    /XD ".venv" "__pycache__" ".pytest_cache" "logs" "tests" `
    /XF "*.pyc" "*.db" | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Error "robocopy failed ($LASTEXITCODE)"; exit 1 }
$global:LASTEXITCODE = 0

# 5) Import self-check (catches missing deps) ------------------------------
Write-Host "Self-check: importing backend app with the portable runtime..."
$env:VOICE_MASTER_LICENSE_ENFORCED = '1'
& (Join-Path $pyDir 'python.exe') -c "import sys; sys.path.insert(0, r'$dstBackend'); import main; print('IMPORT OK - routes:', sum(1 for r in main.app.routes if getattr(r,'path',None)))"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Import self-check FAILED. Add the missing module to backend/requirements-cpu.txt and re-run."
    exit 1
}

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "OK - backend runtime staged at: $staging  (python/, backend/, ffmpeg/)"
