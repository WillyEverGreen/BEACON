# Tier 2 — Run before any release
$ErrorActionPreference = "Stop"

Write-Host "=== Tier 2: Pre-Release Hardening (PowerShell) ===" -ForegroundColor Cyan

Write-Host "1. Auth boundary security test..."
python -m pytest tests/security/test_auth_boundary.py -v
if ($LASTEXITCODE -ne 0) { throw "Auth boundary test FAILED - RLS may be broken" }

Write-Host "2. Site archetypes (10/10 check)..."
python evaluation/validate_site_archetypes.py
if ($LASTEXITCODE -ne 0) { throw "Site archetypes check failed" }

Write-Host "2. All scan modes integration..."
python -m pytest tests/integration/test_phase20_all_modes.py -q --timeout=300
if ($LASTEXITCODE -ne 0) { throw "Integration tests failed" }

Write-Host "3. Contrast-Finder correctness..."
python -c "
from app.services.contrast_finder import find_accessible_color, get_contrast_ratio, hex_to_rgb
fg = '#767676'
bg = '#FFFFFF'
new_fg = find_accessible_color(fg, bg, target_ratio=4.5)
ratio = get_contrast_ratio(hex_to_rgb(new_fg), hex_to_rgb(bg))
assert ratio >= 4.5, f'Ratio {ratio} below 4.5'
print(f'Contrast-Finder OK: {fg} -> {new_fg} (Ratio: {ratio:.2f})')
"
if ($LASTEXITCODE -ne 0) { throw "Contrast-Finder check failed" }

Write-Host "4. IBM engine check..."
python -c "
from app.services.ibm_checker import run_ibm_scan_url
print('IBM OK')
"
if ($LASTEXITCODE -ne 0) { throw "IBM engine check failed" }

Write-Host "5. Cognitive engine experimental flag check..."
python -c "
import re
content = open('app/services/cognitive_checks.py').read()
if re.search(r'experimental\s*=\s*True', content):
    print('Found experimental=True flag in cognitive_checks.py')
    exit(1)
print('Cognitive OK')
"
if ($LASTEXITCODE -ne 0) { throw "Cognitive flag check failed" }

Write-Host "6. A11YBench regression..."
python evaluation/benchmark_a11ybench.py
if ($LASTEXITCODE -ne 0) { throw "A11YBench regression failed" }

Write-Host "=== TIER 2 PASSED ===" -ForegroundColor Green
