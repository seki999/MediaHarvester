$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskTools = Join-Path $taskRoot '.dev-tools'
New-Item -ItemType Directory -Force -Path $taskTools | Out-Null
$taskArchive = Join-Path $taskTools 'aria2.zip'
Invoke-WebRequest -Uri 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip' -OutFile $taskArchive
$taskHash = (Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash
if ($taskHash -ne '67D015301EEF0B612191212D564C5BB0A14B5B9C4796B76454276A4D28D9B288') { throw 'Unexpected aria2 archive hash' }
Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskTools -Force
Write-Host 'aria2 development fixture installed; not bundled in release.'
