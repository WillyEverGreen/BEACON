import asyncio
import uuid

import pytest

from app.db.repository import get_audit_history, persist_audit_payload

pytestmark = [pytest.mark.integration]

@pytest.mark.asyncio
async def test_supabase_persistence_e2e():
    """
    End-to-end integration test for Supabase persistence.
    Verifies that the engine can write to the DB (using user_id=None for FK safety).
    """
    print("\n[DB TEST] Starting Supabase E2E Persistence Check...")
    
    # 1. SETUP TEST DATA
    unique_id = uuid.uuid4().hex[:8]
    test_url = f"https://e2e-test-{unique_id}.beacon.ai"
    
    payload = {
        "url": test_url,
        "score": 88.5,
        "scan_mode": "fast",
        "pages_audited": 1,
        "summary": "Integration Test Payload",
        "issues": [
            {
                "rule_id": f"e2e-rule-{unique_id}",
                "severity": "critical",
                "wcag_criterion": "1.1.1",
                "confidence": 0.95,
                "fix": {"proposed": "Fix it"}
            }
        ]
    }
    
    # 2. PERSIST
    try:
        print(f"[DB TEST] Persisting audit for {test_url} (user_id=None for FK safety)")
        # We pass user_id=None because we don't have a real auth.user row in this test env
        audit_id = persist_audit_payload(payload, user_id=None)
        if audit_id is None:
            pytest.skip("Supabase is unreachable or not configured in current environment")
        assert audit_id is not None

        print(f"[DB TEST] Successfully persisted: {audit_id}")
        
        # 3. RETRIEVE & VERIFY
        print("[DB TEST] Verifying retrieval...")
        history = get_audit_history(test_url, limit=1)
        
        if not history:
            pytest.fail(f"Audit {audit_id} not found in history for {test_url}")
            
        record = history[0]
        assert record["id"] == audit_id
        assert record["score"] == 88.5
        
        print(f"[DB TEST] PASSED: Audit {audit_id} successfully stored and retrieved.")
        
    except Exception as e:
        if "getaddrinfo failed" in str(e) or "connecterror" in type(e).__name__.lower():
            pytest.skip(f"Supabase is unreachable in current environment: {e}")
        pytest.fail(f"Supabase Persistence E2E failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_supabase_persistence_e2e())
