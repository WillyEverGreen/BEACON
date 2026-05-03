# Tier 1 — Run before every push (must all pass)
$ErrorActionPreference = "Stop"

Write-Host "=== Tier 1: Quick Push Verification (PowerShell) ===" -ForegroundColor Cyan

Write-Host "1. Syntax check core modules..."
python -m py_compile app/config.py app/services/audit_runner.py app/services/static_checks.py app/services/ibm_checker.py app/services/contrast_finder.py app/services/cognitive_checks.py
if ($LASTEXITCODE -ne 0) { throw "Syntax check failed" }

Write-Host "2. Unit tests..."
python -m pytest tests/unit/ -q
if ($LASTEXITCODE -ne 0) { throw "Unit tests failed" }

Write-Host "2b. Static checker tests..."
python -m pytest tests/unit/test_static_checker.py -v
if ($LASTEXITCODE -ne 0) { throw "Static checker tests failed" }

Write-Host "3. ACT benchmark..."
python evaluation/benchmark_act.py --profile production
if ($LASTEXITCODE -ne 0) { throw "ACT benchmark failed" }

Write-Host "4. WebAIM Six detection..."
python -m pytest tests/unit/test_webaim_six.py -v
if ($LASTEXITCODE -ne 0) { throw "WebAIM Six tests failed" }

Write-Host "5. Fast mode smoke test..."
python -m pytest tests/integration/test_phase20_all_modes.py -k "fast" -q --timeout=90
if ($LASTEXITCODE -ne 0) { throw "Fast mode smoke test failed" }

Write-Host "=== TIER 1 PASSED ===" -ForegroundColor Green
