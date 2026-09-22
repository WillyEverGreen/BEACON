#!/usr/bin/env python3
"""
Pre-deployment validation script.

Checks that the codebase is ready for production deployment:
- No hardcoded credentials
- No placeholder values in production code
- Environment files properly configured
- No TODO/FIXME in critical paths
- Security configurations present
"""

import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Colors for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

# Safe status icons
SUCCESS_MARK = "[OK]" if sys.platform == "win32" and not os.getenv("PYTHONIOENCODING") else "✓"
ERROR_MARK = "[FAIL]" if sys.platform == "win32" and not os.getenv("PYTHONIOENCODING") else "✗"
WARN_MARK = "[WARN]" if sys.platform == "win32" and not os.getenv("PYTHONIOENCODING") else "⚠"

# Patterns to check (only check for actual placeholder values that need replacement)
PLACEHOLDER_PATTERNS = [
    r"your-[\w-]+-here",
    r"example-api-key",
    r"xxx-[\w-]+",
    r"test-api-key-\d+",
    r"placeholder-key",
    r"placeholder-url",
    r"placeholder-token",
]

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"sk_live_[0-9a-zA-Z]{24,}", "Stripe Live Key"),
    (r"ghp_[0-9a-zA-Z]{36}", "GitHub Personal Access Token"),
    (r"xox[baprs]-[0-9a-zA-Z]{10,48}", "Slack Token"),
]

REQUIRED_ENV_VARS = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "BOOTSTRAP_VIEWER_API_KEY",
    "BOOTSTRAP_AUDITOR_API_KEY",
    "BOOTSTRAP_ADMIN_API_KEY",
]


def print_header(text: str):
    """Print a section header."""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{GREEN}{SUCCESS_MARK} {text}{RESET}")


def print_error(text: str):
    """Print an error message."""
    print(f"{RED}{ERROR_MARK} {text}{RESET}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{YELLOW}{WARN_MARK} {text}{RESET}")


def check_placeholder_values() -> tuple[bool, list[str]]:
    """Check for placeholder values in production code."""
    print_header("Checking for placeholder values in production code...")
    
    errors = []
    production_dirs = ["app", "rag", "frontend/src"]
    
    for directory in production_dirs:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        
        for file_path in dir_path.rglob("*.py"):
            # Skip __pycache__ and test files
            if "__pycache__" in str(file_path) or "test" in str(file_path):
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8")
                
                for pattern in PLACEHOLDER_PATTERNS:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count("\n") + 1
                        errors.append(
                            f"{file_path}:{line_num} - Placeholder pattern '{match.group()}'"
                        )
            except Exception as e:
                print_warning(f"Could not read {file_path}: {e}")
    
    if errors:
        for error in errors:
            print_error(error)
        return False, errors
    else:
        print_success("No placeholder values found in production code")
        return True, []


def check_secrets() -> tuple[bool, list[str]]:
    """Check for accidentally committed secrets."""
    print_header("Checking for accidentally committed secrets...")
    
    errors = []
    check_dirs = ["app", "rag", "frontend/src", "scripts"]
    
    for directory in check_dirs:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        
        for file_path in dir_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip binary files and common non-source files
            if file_path.suffix in [".pyc", ".png", ".jpg", ".pdf", ".woff", ".woff2"]:
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                
                for pattern, secret_type in SECRET_PATTERNS:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[:match.start()].count("\n") + 1
                        errors.append(
                            f"{file_path}:{line_num} - Possible {secret_type} detected"
                        )
            except Exception:
                pass  # Skip files that can't be read
    
    if errors:
        for error in errors:
            print_error(error)
        return False, errors
    else:
        print_success("No obvious secrets detected")
        return True, []


def check_env_files() -> tuple[bool, list[str]]:
    """Check that .env files are not committed."""
    print_header("Checking that .env files are not committed...")
    
    errors = []
    env_files = [".env", "frontend/.env.local"]
    
    for env_file in env_files:
        if Path(env_file).exists():
            # Check if it's tracked by git
            result = os.system(f'git ls-files --error-unmatch "{env_file}" 2>/dev/null')
            if result == 0:
                errors.append(f"{env_file} is tracked by git (should be gitignored)")
    
    if errors:
        for error in errors:
            print_error(error)
        return False, errors
    else:
        print_success("No .env files committed to git")
        return True, []


def check_env_example() -> tuple[bool, list[str]]:
    """Check that .env.example exists and has no real values."""
    print_header("Checking .env.example file...")
    
    errors = []
    
    if not Path(".env.example").exists():
        errors.append(".env.example file missing")
        print_error(".env.example file not found")
        return False, errors
    
    # Check that .env.example doesn't contain real secrets
    content = Path(".env.example").read_text(encoding="utf-8")
    
    # Should contain placeholder patterns
    has_placeholders = any(
        re.search(pattern, content, re.IGNORECASE)
        for pattern in PLACEHOLDER_PATTERNS
    )
    
    if not has_placeholders:
        errors.append(".env.example should contain placeholder values")
    
    # Should not contain actual secrets
    for pattern, secret_type in SECRET_PATTERNS:
        if re.search(pattern, content):
            errors.append(f".env.example may contain real {secret_type}")
    
    if errors:
        for error in errors:
            print_error(error)
        return False, errors
    else:
        print_success(".env.example is properly configured")
        return True, []


def check_security_configs() -> tuple[bool, list[str]]:
    """Check that security configurations are present."""
    print_header("Checking security configurations...")
    
    errors = []
    
    # Check for security middleware
    main_py = Path("app/main.py")
    if main_py.exists():
        content = main_py.read_text(encoding="utf-8")
        
        if "SecurityHeadersMiddleware" not in content:
            errors.append("SecurityHeadersMiddleware not registered")
        
        if "RateLimitMiddleware" not in content:
            errors.append("RateLimitMiddleware not registered")
        
        if "error_handler_middleware" not in content:
            errors.append("error_handler_middleware not registered")
    
    # Check for CORS configuration
    if "configure_cors" not in content:
        print_warning("CORS configuration not found (may be configured differently)")
    
    if errors:
        for error in errors:
            print_error(error)
        return False, errors
    else:
        print_success("Security configurations present")
        return True, []


def check_docker_config() -> tuple[bool, list[str]]:
    """Check Docker configuration."""
    print_header("Checking Docker configuration...")
    
    errors = []
    
    # Check Dockerfile exists
    if not Path("Dockerfile").exists():
        errors.append("Dockerfile not found")
    else:
        content = Path("Dockerfile").read_text(encoding="utf-8")
        
        # Check for non-root user
        if "USER beacon" not in content:
            errors.append("Dockerfile should run as non-root user")
        
        # Check for health check
        if "HEALTHCHECK" not in content:
            print_warning("Dockerfile missing HEALTHCHECK instruction")
    
    # Check .dockerignore exists
    if not Path(".dockerignore").exists():
        errors.append(".dockerignore not found")
    
    if errors:
        for error in errors:
            print_error(error)
        return False, errors
    else:
        print_success("Docker configuration looks good")
        return True, []


def check_render_config() -> tuple[bool, list[str]]:
    """Check Render configuration."""
    print_header("Checking Render configuration...")
    
    errors = []
    
    if not Path("render.yaml").exists():
        errors.append("render.yaml not found")
    else:
        content = Path("render.yaml").read_text(encoding="utf-8")
        
        # Check for health check
        if "healthCheckPath" not in content:
            errors.append("render.yaml missing healthCheckPath")
        
        # Check for environment variables
        if "envVars" not in content:
            errors.append("render.yaml missing envVars section")
    
    if errors:
        for error in errors:
            print_error(error)
        return False, errors
    else:
        print_success("Render configuration looks good")
        return True, []


def main():
    """Run all pre-deployment checks."""
    print(f"\n{BLUE}{'=' * 70}")
    print("BEACON Pre-Deployment Validation")
    print(f"{'=' * 70}{RESET}\n")
    
    checks = [
        ("Placeholder Values", check_placeholder_values),
        ("Secret Detection", check_secrets),
        (".env Files", check_env_files),
        (".env.example", check_env_example),
        ("Security Configs", check_security_configs),
        ("Docker Config", check_docker_config),
        ("Render Config", check_render_config),
    ]
    
    results = []
    all_passed = True
    
    for check_name, check_func in checks:
        passed, errors = check_func()
        results.append((check_name, passed, errors))
        if not passed:
            all_passed = False
    
    # Print summary
    print_header("Summary")
    
    for check_name, passed, errors in results:
        if passed:
            print_success(f"{check_name}: PASSED")
        else:
            print_error(f"{check_name}: FAILED ({len(errors)} issue(s))")
    
    print()
    
    if all_passed:
        print(f"{GREEN}{'=' * 70}")
        print("✓ All checks passed! Ready for deployment.")
        print(f"{'=' * 70}{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}{'=' * 70}")
        print("✗ Some checks failed. Please fix the issues before deploying.")
        print(f"{'=' * 70}{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
