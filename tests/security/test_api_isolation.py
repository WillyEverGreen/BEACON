# tests/security/test_api_isolation.py
import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
import uuid

# Mock JWT payloads for testing
USER_A_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLWEtMTIzIn0.sig"
USER_B_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLWItNDU2In0.sig"

client = TestClient(app)

@pytest.fixture
def auth_headers_a():
    return {
        "X-API-Key": "beacon_admin_key",
        "X-Supabase-Token": USER_A_TOKEN,
    }

@pytest.fixture
def auth_headers_b():
    return {
        "X-API-Key": "beacon_admin_key",
        "X-Supabase-Token": USER_B_TOKEN,
    }

def test_api_user_isolation(auth_headers_a, auth_headers_b):
    """Verify that User A cannot see User B's projects via API."""
    # 1. User A creates a project
    create_res = client.post(
        "/api/projects/",
        json={"name": "Project A", "url": "https://a.com"},
        headers=auth_headers_a
    )
    assert create_res.status_code == 200
    project_id = create_res.json()["id"]

    # 2. User B tries to list projects - should not see Project A
    list_res = client.get("/api/projects/", headers=auth_headers_b)
    assert list_res.status_code == 200
    project_ids = [p["id"] for p in list_res.json()]
    assert project_id not in project_ids, "API FAILURE: User B can list User A's project"

    # 3. User B tries to get Project A directly - should be 404
    get_res = client.get(f"/api/projects/{project_id}", headers=auth_headers_b)
    assert get_res.status_code == 404

    # 4. User B tries to delete Project A - should be 404
    del_res = client.delete(f"/api/projects/{project_id}", headers=auth_headers_b)
    assert del_res.status_code == 404

    # 5. User A can still see it
    get_res_a = client.get(f"/api/projects/{project_id}", headers=auth_headers_a)
    assert get_res_a.status_code == 200
    assert get_res_a.json()["id"] == project_id

    # Cleanup
    client.delete(f"/api/projects/{project_id}", headers=auth_headers_a)
