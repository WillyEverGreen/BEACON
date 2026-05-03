import asyncio
import os
import uuid
from app.db.repository import persist_audit_payload, get_audit_history
from app.config import settings

async def test_supabase_write():
    print("Starting Supabase E2E Write Test...")
    
    # Create a dummy payload
    audit_id = uuid.uuid4().hex
    payload = {
        "audit_id": audit_id,
        "url": "https://e2e-test.beacon.ai",
        "score": 99.0,
        "scan_mode": "fast",
        "pages_audited": 1,
        "summary": "E2E Test Summary",
        "issues": [
            {
                "rule_id": "test-rule",
                "severity": "minor",
                "element": "body",
                "description": "Test issue"
            }
        ],
        "earl_report": {"@context": "https://www.w3.org/ns/earl"}
    }
    
    try:
        print(f"Attempting to persist audit {audit_id}...")
        # Note: persist_audit_payload is synchronous in repository.py 
        # (uses sb.table().upsert().execute() which is sync in supabase-py)
        # Wait, repository.py uses get_supabase() which returns a sync client.
        
        from app.db.repository import persist_audit_payload
        returned_id = persist_audit_payload(payload, status="completed")
        print(f"Persisted audit ID: {returned_id}")
        
        print("Verifying retrieval...")
        recent = get_audit_history("https://e2e-test.beacon.ai", limit=5)
        found = any(s.get("score") == 99.0 for s in recent)
        
        if found:
            print("DB OK: Audit found in history.")
        else:
            print("DB FAIL: Audit NOT found in history. Check RLS or connection.")
            print(f"Recent history: {recent}")
            
    except Exception as e:
        print(f"DB ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_supabase_write())
