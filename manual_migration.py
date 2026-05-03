import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY must be set.")
    exit(1)

supabase: Client = create_client(url, key)

sql = """
ALTER TABLE audits ADD COLUMN IF NOT EXISTS earl_report JSONB DEFAULT '{}';
"""

print(f"Attempting to add 'earl_report' column to 'audits' table at {url}...")

try:
    # The Supabase-py client doesn't have a direct 'execute' for raw SQL unless via RPC.
    # We'll try a dummy insert/update to see if the column exists, or use the REST API if possible.
    # However, for DDL, we really need the SQL API.
    
    import requests
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "apikey": key
    }
    
    # Note: Supabase's /rest/v1/rpc/ is for functions. 
    # To run raw SQL, usually you use the SQL API on port 5432 or the dashboard.
    # Some setups have an 'exec_sql' RPC function.
    
    print("Checking if column 'earl_report' already exists...")
    try:
        # Try a simple select to check column existence
        res = supabase.table("audits").select("earl_report").limit(1).execute()
        print("Column 'earl_report' already exists. Migration not needed.")
    except Exception as e:
        if "column audits.earl_report does not exist" in str(e).lower() or "earl_report" in str(e).lower():
            print("Column 'earl_report' is missing. You need to add it via the Supabase SQL Editor:")
            print(sql)
            print("-" * 40)
            print("Please run the SQL above in your Supabase Dashboard SQL Editor.")
        else:
            print(f"Unexpected error checking column: {e}")

except Exception as e:
    print(f"Migration failed: {e}")
