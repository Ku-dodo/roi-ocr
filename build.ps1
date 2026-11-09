param(
    [string]$PythonExecutable = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "Python executable not found: $PythonExecutable"
}

$BuildDirectory = Join-Path $ProjectRoot "build"
New-Item -ItemType Directory -Path $BuildDirectory -Force | Out-Null

& $PythonExecutable ".\tools\collect_licenses.py"
if ($LASTEXITCODE -ne 0) { throw "Failed to collect license materials." }

& $PythonExecutable -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name "OCRTool" `
    --specpath $BuildDirectory `
    --contents-directory "_internal" `
    --paths ".\src" `
    --collect-all "easyocr" `
    --collect-all "torchvision" `
    ".\main.py"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$DistributionRoot = ".\dist\OCRTool"
Copy-Item -LiteralPath ".\licenses" -Destination "$DistributionRoot\licenses" -Recurse -Force
Copy-Item -LiteralPath ".\README.md" -Destination "$DistributionRoot\README.md" -Force
Copy-Item -LiteralPath ".\THIRD_PARTY_NOTICES.md" -Destination "$DistributionRoot\THIRD_PARTY_NOTICES.md" -Force

Write-Host "Build complete: $DistributionRoot\OCRTool.exe"
