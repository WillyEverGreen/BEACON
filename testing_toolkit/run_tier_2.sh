#!/bin/bash
set -e
# Add Miniconda to PATH (handles both WSL and Git Bash mounts)
export PATH="/mnt/c/Users/advdi/miniconda3:/mnt/c/Users/advdi/miniconda3/Scripts:/c/Users/advdi/miniconda3:/c/Users/advdi/miniconda3/Scripts:$PATH"

# Auto-detect Python executable with pytest installed
for cmd in "python" "python.exe" "python3" "py"; do
    if command -v $cmd >/dev/null 2>&1; then
        if $cmd -m pytest --version >/dev/null 2>&1; then
            PYTHON=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python with pytest not found in PATH."
    exit 1
fi

echo "=== Tier 2: Pre-Release Hardening (Using $PYTHON) ==="

echo "1. Site archetypes (10/10 check)..."
$PYTHON evaluation/validate_site_archetypes.py

echo "2. All scan modes integration..."
$PYTHON -m pytest tests/integration/test_phase20_all_modes.py -q --timeout=300

echo "3. Contrast-Finder correctness..."
$PYTHON -c "
from app.services.contrast_finder import find_accessible_color, get_contrast_ratio, hex_to_rgb
fg = '#767676'
bg = '#FFFFFF'
new_fg = find_accessible_color(fg, bg, target_ratio=4.5)
ratio = get_contrast_ratio(hex_to_rgb(new_fg), hex_to_rgb(bg))
assert ratio >= 4.5, f'Ratio {ratio} below 4.5'
print(f'Contrast-Finder OK: {fg} -> {new_fg} (Ratio: {ratio:.2f})')
"

echo "4. IBM engine check..."
$PYTHON -c "
from app.services.ibm_checker import run_ibm_scan_url
print('IBM OK')
"

echo "5. Cognitive engine experimental flag check..."
$PYTHON -c "
import re
content = open('app/services/cognitive_checks.py').read()
if re.search(r'experimental\s*=\s*True', content):
    print('Found experimental=True flag in cognitive_checks.py')
    exit(1)
print('Cognitive OK')
"

echo "6. A11YBench regression..."
$PYTHON evaluation/benchmark_a11ybench.py

echo "=== TIER 2 PASSED ==="
