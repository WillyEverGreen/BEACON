# tests/security/test_auth_boundary.py
import os
import uuid

import pytest
from dotenv import load_dotenv

from supabase import create_client

# Load environment variables from .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY")

@pytest.fixture
def client_a():
    if not os.environ.get("TEST_USER_A_EMAIL"):
        pytest.skip("TEST_USER_A_EMAIL not set in environment")
    try:
        client = create_client(SUPABASE_URL, ANON_KEY)
        client.auth.sign_in_with_password({
            "email": os.environ["TEST_USER_A_EMAIL"],
            "password": os.environ["TEST_USER_A_PASSWORD"]
        })
        return client
    except Exception as e:
        pytest.skip(f"Supabase service unreachable for client_a: {e}")

@pytest.fixture
def client_b():
    if not os.environ.get("TEST_USER_B_EMAIL"):
        pytest.skip("TEST_USER_B_EMAIL not set in environment")
    try:
        client = create_client(SUPABASE_URL, ANON_KEY)
        client.auth.sign_in_with_password({
            "email": os.environ["TEST_USER_B_EMAIL"],
            "password": os.environ["TEST_USER_B_PASSWORD"]
        })
        return client
    except Exception as e:
        pytest.skip(f"Supabase service unreachable for client_b: {e}")

@pytest.fixture
def anon_client():
    if not SUPABASE_URL or not ANON_KEY:
        pytest.skip("Supabase credentials not configured")
    try:
        return create_client(SUPABASE_URL, ANON_KEY)
    except Exception as e:
        pytest.skip(f"Supabase service unreachable for anon_client: {e}")

def test_user_cannot_see_other_users_projects(client_a, client_b):
    """User A's projects must not be visible to User B."""
    project_id = f"test-{uuid.uuid4().hex[:8]}"
    user_a_id = client_a.auth.get_user().user.id

    # User A creates a project
    client_a.table("projects").insert({
        "id": project_id,
        "name": "User A Secret Project",
        "url": "https://test.example.com",
        "user_id": user_a_id
    }).execute()

    # User B tries to read it
    result = client_b.table("projects").select("*").eq("id", project_id).execute()
    assert len(result.data) == 0, "RLS FAILURE: User B can see User A's project"

    # Cleanup
    client_a.table("projects").delete().eq("id", project_id).execute()

def test_user_cannot_see_other_users_scans(client_a, client_b):
    """User A's scans must not be visible to User B."""
    project_id = f"test-{uuid.uuid4().hex[:8]}"
    scan_id = f"test-scan-{uuid.uuid4().hex[:8]}"
    user_a_id = client_a.auth.get_user().user.id

    # User A creates a project and scan
    client_a.table("projects").insert({
        "id": project_id,
        "name": "User A Project",
        "url": "https://test.example.com",
        "user_id": user_a_id
    }).execute()

    client_a.table("scans").insert({
        "id": scan_id,
        "project_id": project_id,
        "url": "https://test.example.com",
        "user_id": user_a_id
    }).execute()

    # User B tries to read it
    result = client_b.table("scans").select("*").eq("id", scan_id).execute()
    assert len(result.data) == 0, "RLS FAILURE: User B can see User A's scan"

    # Cleanup
    client_a.table("scans").delete().eq("id", scan_id).execute()
    client_a.table("projects").delete().eq("id", project_id).execute()

def test_unauthenticated_cannot_read_projects(anon_client):
    """Unauthenticated requests return empty data or permission denied."""
    try:
        result = anon_client.table("projects").select("*").execute()
        assert len(result.data) == 0, "RLS FAILURE: Anon can see projects"
    except Exception as e:
        if "getaddrinfo failed" in str(e) or "connecterror" in type(e).__name__.lower():
            pytest.skip(f"Supabase unreachable: {e}")
        # Permission denied is also an acceptable outcome for unauthenticated users
        assert "permission denied" in str(e).lower() or "42501" in str(e)

def test_unauthenticated_cannot_read_scans(anon_client):
    """Unauthenticated requests return empty data or permission denied."""
    try:
        result = anon_client.table("scans").select("*").execute()
        assert len(result.data) == 0, "RLS FAILURE: Anon can see scans"
    except Exception as e:
        if "getaddrinfo failed" in str(e) or "connecterror" in type(e).__name__.lower():
            pytest.skip(f"Supabase unreachable: {e}")
        assert "permission denied" in str(e).lower() or "42501" in str(e)

def test_user_can_see_own_projects(client_a):
    """User A can read their own projects."""
    project_id = f"test-{uuid.uuid4().hex[:8]}"
    user_a_id = client_a.auth.get_user().user.id

    client_a.table("projects").insert({
        "id": project_id,
        "name": "My Project",
        "url": "https://test.example.com",
        "user_id": user_a_id
    }).execute()

    result = client_a.table("projects").select("*").eq("id", project_id).execute()
    assert len(result.data) == 1, "User A cannot see their own project"

    # Cleanup
    client_a.table("projects").delete().eq("id", project_id).execute()
