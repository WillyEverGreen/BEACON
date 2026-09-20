#!/usr/bin/env python3
"""
Script to replace print() statements with proper logging in production code.

This script:
1. Finds all print() calls in app/ and rag/ directories
2. Replaces them with appropriate logger calls
3. Adds logger imports where needed
4. Preserves test files (uses print for test output)
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def should_process_file(file_path: Path) -> bool:
    """Determine if a file should be processed."""
    # Skip test files - they can use print()
    if "test" in file_path.name.lower() or "test" in str(file_path.parent):
        return False
    
    # Skip scratch and evaluation directories
    excluded_dirs = {"scratch", "evaluation", "tests"}
    if any(excluded in file_path.parts for excluded in excluded_dirs):
        return False
    
    # Only process Python files in app/ and rag/ directories
    if file_path.suffix != ".py":
        return False
    
    return any(part in file_path.parts for part in ("app", "rag"))


def has_logger_import(content: str) -> bool:
    """Check if file already has logger import."""
    return bool(re.search(r"^import logging", content, re.MULTILINE) or 
                re.search(r"^from .* import .*logging", content, re.MULTILINE))


def has_logger_definition(content: str) -> bool:
    """Check if file already has logger definition."""
    return bool(re.search(r"logger\s*=\s*logging\.getLogger", content))


def add_logger_import(content: str) -> str:
    """Add logging import and logger definition to file."""
    lines = content.split("\n")
    
    # Find the right place to insert (after docstring and existing imports)
    insert_idx = 0
    in_docstring = False
    last_import_idx = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Track docstrings
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if in_docstring:
                in_docstring = False
                insert_idx = i + 1
            else:
                in_docstring = True
            continue
        
        # Track imports
        if stripped.startswith(("import ", "from ")) and not in_docstring:
            last_import_idx = i
    
    # Insert after last import, or after docstring if no imports
    insert_idx = max(insert_idx, last_import_idx + 1)
    
    # Check if logging is already imported
    has_logging = has_logger_import(content)
    has_logger_def = has_logger_definition(content)
    
    additions = []
    if not has_logging:
        additions.append("import logging")
    if not has_logger_def:
        additions.append("\nlogger = logging.getLogger(__name__)")
    
    if additions:
        lines.insert(insert_idx, "\n".join(additions))
        if insert_idx < len(lines) - 1 and lines[insert_idx + 1].strip():
            lines.insert(insert_idx + 1, "")
    
    return "\n".join(lines)


def determine_log_level(message: str) -> str:
    """
    Determine appropriate log level based on message content.
    """
    message_lower = message.lower()
    
    # Error indicators
    if any(word in message_lower for word in ["error", "failed", "failure", "exception", "critical"]):
        return "error"
    
    # Warning indicators  
    if any(word in message_lower for word in ["warning", "warn", "deprecated", "issue"]):
        return "warning"
    
    # Debug indicators (internal details, verbose output)
    if any(word in message_lower for word in ["debug", "trace", "verbose", "detail"]):
        return "debug"
    
    # Default to info for general messages
    return "info"


def replace_print_statement(match: re.Match) -> str:
    """
    Replace a single print() call with appropriate logger call.
    """
    full_match = match.group(0)
    args = match.group(1)
    
    # Try to extract the message to determine log level
    # Handle f-strings, regular strings, and expressions
    message = args.strip()
    if message.startswith(('f"', "f'")):
        # Extract content from f-string for analysis
        content = re.sub(r'f["\'](.+?)["\']', r'\1', message)
        log_level = determine_log_level(content)
    elif message.startswith(('"', "'")):
        # Regular string
        content = message[1:-1] if len(message) > 2 else message
        log_level = determine_log_level(content)
    else:
        # Expression or variable - default to info
        log_level = "info"
    
    # Replace print(...) with logger.level(...)
    return f"logger.{log_level}({args})"


def process_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, int]:
    """
    Process a single file, replacing print statements with logging.
    
    Returns:
        Tuple of (was_modified, num_replacements)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        
        # Find all print statements
        print_pattern = r"\bprint\(((?:[^()]|\([^()]*\))*)\)"
        matches = list(re.finditer(print_pattern, content))
        
        if not matches:
            return False, 0
        
        # Replace print statements
        content = re.sub(print_pattern, replace_print_statement, content)
        
        # Add logger import if needed
        if not has_logger_import(content) or not has_logger_definition(content):
            content = add_logger_import(content)
        
        # Write back if not dry run
        if not dry_run and content != original_content:
            file_path.write_text(content, encoding="utf-8")
            return True, len(matches)
        
        return content != original_content, len(matches)
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False, 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Replace print() with logging in production code")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    parser.add_argument("--path", default=".", help="Base path to search (default: current directory)")
    args = parser.parse_args()
    
    base_path = Path(args.path).resolve()
    
    # Find all Python files to process
    python_files = [
        f for f in base_path.rglob("*.py")
        if should_process_file(f)
    ]
    
    print(f"Found {len(python_files)} Python files to process")
    if args.dry_run:
        print("DRY RUN MODE - no files will be modified\n")
    
    total_modified = 0
    total_replacements = 0
    
    for file_path in sorted(python_files):
        was_modified, num_replacements = process_file(file_path, dry_run=args.dry_run)
        
        if was_modified:
            total_modified += 1
            total_replacements += num_replacements
            status = "[DRY RUN]" if args.dry_run else "[MODIFIED]"
            rel_path = file_path.relative_to(base_path)
            print(f"{status} {rel_path}: {num_replacements} print statements replaced")
    
    print(f"\nSummary:")
    print(f"  Files modified: {total_modified}")
    print(f"  Total print statements replaced: {total_replacements}")
    
    if args.dry_run:
        print("\nRun without --dry-run to apply changes")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
