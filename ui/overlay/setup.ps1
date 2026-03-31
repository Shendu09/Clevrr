# Install Electron overlay dependencies (Windows)
# Run from project root: .\ui\overlay\setup.ps1

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Installing Clevrr Overlay Dependencies" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$overlayPath = "$PSScriptRoot"
Push-Location $overlayPath

# Check for Node.js
Write-Host "[1/3] Checking for Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Node.js is not installed" -ForegroundColor Red
    Write-Host "Install from https://nodejs.org/" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  Node.js version: $nodeVersion" -ForegroundColor Green

# Install npm packages
Write-Host ""
Write-Host "[2/3] Installing npm packages..." -ForegroundColor Yellow
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: npm install failed" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  NPM packages installed" -ForegroundColor Green

# Verify Electron
Write-Host ""
Write-Host "[3/3] Verifying Electron..." -ForegroundColor Yellow
$electronVersion = npx electron --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Electron not found" -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "  Electron version: $electronVersion" -ForegroundColor Green

Pop-Location

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To launch Clevrr with Electron overlay:" -ForegroundColor Green
Write-Host "  python main.py --ui overlay" -ForegroundColor Green
Write-Host ""
