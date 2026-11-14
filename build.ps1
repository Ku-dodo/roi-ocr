param(
    [string]$PythonExecutable = ".\.venv-release\Scripts\python.exe",
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "Python executable not found: $PythonExecutable"
}
if ($Version -notmatch '^\d+\.\d+\.\d+([-.][0-9A-Za-z.-]+)?$') {
    throw "Invalid version: $Version"
}

$BuildDirectory = Join-Path $ProjectRoot "build"
New-Item -ItemType Directory -Path $BuildDirectory -Force | Out-Null

$GeneratedLicenses = Join-Path $ProjectRoot "licenses\generated"
if (Test-Path -LiteralPath $GeneratedLicenses) {
    Remove-Item -LiteralPath $GeneratedLicenses -Recurse -Force
}

& $PythonExecutable ".\tools\collect_licenses.py"
if ($LASTEXITCODE -ne 0) { throw "Failed to collect license materials." }

& $PythonExecutable ".\tools\build_app_icon.py"
if ($LASTEXITCODE -ne 0) { throw "Failed to render application icon." }

& $PythonExecutable -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name "OCRTool" `
    --icon "$ProjectRoot\src\ocr_app\presentation\assets\app.ico" `
    --add-data "$ProjectRoot\src\ocr_app\presentation\assets;ocr_app\presentation\assets" `
    --specpath $BuildDirectory `
    --contents-directory "_internal" `
    --paths "$ProjectRoot\src" `
    --collect-all "easyocr" `
    --collect-all "torchvision" `
    ".\main.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$DistributionRoot = ".\dist\OCRTool"
Copy-Item -LiteralPath ".\licenses" -Destination "$DistributionRoot\licenses" -Recurse -Force
Copy-Item -LiteralPath ".\README.md" -Destination "$DistributionRoot\README.md" -Force
Copy-Item -LiteralPath ".\LICENSE" -Destination "$DistributionRoot\LICENSE" -Force
Copy-Item -LiteralPath ".\THIRD_PARTY_NOTICES.md" -Destination "$DistributionRoot\THIRD_PARTY_NOTICES.md" -Force

$ArchivePath = Join-Path $ProjectRoot "dist\OCRTool-$Version-windows-x64.zip"
if (Test-Path -LiteralPath $ArchivePath) {
    Remove-Item -LiteralPath $ArchivePath -Force
}
Compress-Archive -LiteralPath $DistributionRoot -DestinationPath $ArchivePath -CompressionLevel Optimal

$ChecksumPath = "$ArchivePath.sha256"
$ArchiveHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $ChecksumPath -Value "$ArchiveHash  $(Split-Path -Leaf $ArchivePath)" -Encoding ascii

Write-Host "Build complete: $DistributionRoot\OCRTool.exe"
Write-Host "Release archive: $ArchivePath"
Write-Host "SHA-256: $ChecksumPath"
