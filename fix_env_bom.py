#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def fix_env_bom(filepath):
    """Remove UTF-8 BOM from .env file."""
    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
        
        # Check for BOM
        if raw.startswith(b'\xef\xbb\xbf'):
            print(f"Found BOM in {filepath}, removing...")
            clean = raw[3:]  # Skip BOM bytes
            with open(filepath, 'wb') as f:
                f.write(clean)
            print(f"✓ Fixed {filepath}")
            return True
        else:
            print(f"No BOM found in {filepath}")
            return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

# Check current directory and parent directories
paths_to_check = [
    ".env",
    os.path.expanduser("~/.env"),
    os.path.expanduser("~/.env.local"),
]

# Also check the crawl4ai package
try:
    import crawl4ai
    crawl4ai_dir = Path(crawl4ai.__file__).parent
    paths_to_check.append(str(crawl4ai_dir / ".env"))
except:
    pass

found_any = False
for path in paths_to_check:
    if os.path.exists(path):
        if fix_env_bom(path):
            found_any = True

if not found_any:
    print("No .env files with BOM found, but checking if any .env exists...")
    for path in paths_to_check:
        if os.path.exists(path):
            print(f"  {path} exists")
