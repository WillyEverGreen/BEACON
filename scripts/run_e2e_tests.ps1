#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run Playwright E2E tests for BEACON

.DESCRIPTION
    This script runs the Playwright E2E test suite with various options

.PARAMETER Headed
    Run tests in headed mode (browser visible)

.PARAMETER UI
    Run tests in UI mode (interactive)

.PARAMETER Debug
    Run tests in debug mode

.PARAMETER Project
    Run tests for specific browser project (chromium, firefox, webkit)

.PARAMETER Test
    Run specific test file

.EXAMPLE
    .\scripts\run_e2e_tests.ps1
    .\scripts\run_e2e_tests.ps1 -Headed
    .\scripts\run_e2e_tests.ps1 -UI
    .\scripts\run_e2e_tests.ps1 -Project chromium
    .\scripts\run_e2e_tests.ps1 -Test homepage.spec.ts
#>

param(
    [switch]$Headed,
    [switch]$UI,
    [switch]$Debug,
    [string]$Project = "",
    [string]$Test = "",
    [string]$TargetUrl = "https://example.com",
    [string]$ProjectName = "Example Audit Property"
)

Write-Host "==================================================================" -ForegroundColor Blue
Write-Host "BEACON E2E Testing with Playwright" -ForegroundColor Blue
Write-Host "Target Website: $TargetUrl" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Blue
Write-Host ""

$FrontendDir = Join-Path $PSScriptRoot "..\frontend"
Push-Location $FrontendDir

try {
    # Check if frontend dependencies are installed
    if (-not (Test-Path "node_modules/@playwright/test")) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
        npm install
        npx playwright install chromium
    }

    # Set environment variables for target testing
    $env:TEST_TARGET_URL = $TargetUrl
    $env:TEST_PROJECT_NAME = $ProjectName

    # Build command
    $cmd = "npx playwright test"

    if ($UI) {
        $cmd += " --ui"
    }
    elseif ($Debug) {
        $cmd += " --debug"
    }
    elseif ($Headed) {
        $cmd += " --headed"
    }

    if ($Project) {
        $cmd += " --project=$Project"
    }

    if ($Test) {
        $cmd += " $Test"
    }

    Write-Host "Running: $cmd" -ForegroundColor Cyan
    Write-Host ""

    # Run tests
    Invoke-Expression $cmd

    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "[OK] All tests passed!" -ForegroundColor Green
    Write-Host "==================================================================" -ForegroundColor Green
} else {
    Write-Host "==================================================================" -ForegroundColor Red
    Write-Host "[FAIL] Some tests failed" -ForegroundColor Red
    Write-Host "==================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "View detailed report: npx playwright show-report" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  npx playwright show-report    - View HTML report" -ForegroundColor Gray
Write-Host "  npx playwright test --ui      - Run in UI mode" -ForegroundColor Gray
Write-Host "  npx playwright test --headed  - Run with visible browser" -ForegroundColor Gray
Write-Host "  npx playwright test --debug   - Run in debug mode" -ForegroundColor Gray
Write-Host ""

exit $exitCode
