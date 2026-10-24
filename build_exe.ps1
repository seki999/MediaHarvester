param([switch]$OneFile)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { $taskPython = 'python' }
& $taskPython -c "import PySide6, yt_dlp, httpx, bs4, PIL, PyInstaller, playwright"
if ($LASTEXITCODE -ne 0) { throw 'Install requirements-build.txt first.' }
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $PSScriptRoot '.dev-tools\ms-playwright'
& $taskPython -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed; build stopped.' }
& $taskPython scripts\smoke_deep.py
if ($LASTEXITCODE -ne 0) { throw 'Deep parsing browser smoke failed; build stopped.' }
& $taskPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
& $taskPython scripts\collect_notices.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
$env:MH_ONEFILE = if ($OneFile) { '1' } else { '0' }
$taskOutput = if ($OneFile) { 'dist\onefile' } else { 'dist\onedir' }
& $taskPython -m PyInstaller --noconfirm --distpath $taskOutput mediaharvester.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
Write-Host "Build output: $PSScriptRoot\$taskOutput"
