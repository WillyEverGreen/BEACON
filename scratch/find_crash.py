import os
import subprocess
import sys

def run_test(file_path):
    print(f"Running {file_path}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", file_path, "-q"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"FAILED: {file_path}")
            print(result.stderr)
        else:
            print(f"PASSED: {file_path}")
    except Exception as e:
        print(f"ERROR: {file_path} - {e}")

unit_dir = "tests/unit"
services_dir = "tests/unit/services"

files = [os.path.join(unit_dir, f) for f in os.listdir(unit_dir) if f.startswith("test_") and f.endswith(".py")]
files += [os.path.join(services_dir, f) for f in os.listdir(services_dir) if f.startswith("test_") and f.endswith(".py")]

for f in files:
    run_test(f)
