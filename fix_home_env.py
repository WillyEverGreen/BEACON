import os

# Fix the home directory .env file
home_env = os.path.expanduser("~/.env")

if os.path.exists(home_env):
    with open(home_env, 'rb') as f:
        raw = f.read()
    
    # Remove BOM if present
    if raw.startswith(b'\xef\xbb\xbf'):
        clean = raw[3:]
        with open(home_env, 'wb') as f:
            f.write(clean)
        print(f"Fixed {home_env}")
    else:
        print(f"{home_env} has no BOM")
else:
    print(f"{home_env} not found")
