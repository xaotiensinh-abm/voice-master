# Voice-Master - assemble a portable backend runtime for packaging (K2).
# GPU by default: bundles torch+torchaudio (CUDA) so VieNeu uses the PyTorch
# engine on NVIDIA GPUs (falls back to ONNX/CPU automatically on non-GPU machines).
# Use -Cpu for a lighter ONNX-only bundle (no torch).
#   powershell -ExecutionPolicy Bypass -File scripts\build_backend_runtime.ps1        # GPU
#   powershell -ExecutionPolicy Bypass -File scripts\build_backend_runtime.ps1 -Cpu   # CPU-only
param([switch]$Cpu)
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
$TORCH_INDEX  = 'https://download.pytorch.org/whl/cu121'  # CUDA 12.1 wheels (bundle CUDA libs)

$mode = if ($Cpu) { 'CPU (ONNX, no torch)' } else { 'GPU (torch CUDA)' }
Write-Host "Build mode: $mode"

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
    $pth = Get-ChildItem $pyDir -Filter 'python*._pth' | Select-Object -First 1
    (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName -Encoding ascii
    Write-Host "Installing pip..."
    $getpip = Join-Path $tmp 'get-pip.py'
    Invoke-WebRequest -Uri $GETPIP_URL -OutFile $getpip
    & (Join-Path $pyDir 'python.exe') $getpip --no-warn-script-location
}

$py = Join-Path $pyDir 'python.exe'

# 2) Base dependencies -----------------------------------------------------
Write-Host "Installing base dependencies..."
& $py -m pip install --no-warn-script-location -r (Join-Path $backend 'requirements-base.txt')

# 2b) GPU: torch + torchaudio (CUDA) --------------------------------------
if (-not $Cpu) {
    Write-Host "Installing torch + torchaudio (CUDA) from $TORCH_INDEX (large, several GB)..."
    & $py -m pip install --no-warn-script-location torch torchaudio --index-url $TORCH_INDEX
    Write-Host "torch import check:"
    & $py -c "import torch; print('  torch', torch.__version__, '| cuda build:', torch.version.cuda, '| cuda available:', torch.cuda.is_available())"
    if ($LASTEXITCODE -ne 0) { Write-Error "torch import failed in portable runtime."; exit 1 }
}

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
& $py -c "import sys; sys.path.insert(0, r'$dstBackend'); import main; print('IMPORT OK - routes:', sum(1 for r in main.app.routes if getattr(r,'path',None)))"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Import self-check FAILED. Add the missing module to backend/requirements-base.txt and re-run."
    exit 1
}

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "OK [$mode] - backend runtime staged at: $staging  (python/, backend/, ffmpeg/)"
