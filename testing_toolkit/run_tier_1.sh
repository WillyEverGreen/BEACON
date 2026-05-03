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

echo "=== Tier 1: Quick Push Verification (Using $PYTHON) ==="

echo "1. Syntax check core modules..."
$PYTHON -m py_compile \
  app/config.py \
  app/services/audit_runner.py \
  app/services/static_checks.py \
  app/services/ibm_checker.py \
  app/services/contrast_finder.py \
  app/services/cognitive_checks.py

echo "2. Unit tests..."
$PYTHON -m pytest tests/unit/ -q

echo "2b. Static checker tests..."
$PYTHON -m pytest tests/unit/test_static_checker.py -v

echo "3. ACT benchmark..."
$PYTHON evaluation/benchmark_act.py --profile production

echo "4. WebAIM Six detection..."
$PYTHON -m pytest tests/unit/test_webaim_six.py -v

echo "5. Fast mode smoke test..."
$PYTHON -m pytest tests/integration/test_phase20_all_modes.py -k "fast" -q --timeout=90

echo "=== TIER 1 PASSED ==="
