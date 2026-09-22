#!/usr/bin/env python3
"""
BEACON Deployment Environment Generator.

Generates production-ready, cryptographically secure keys and formats
environment variable configuration blocks for Render (backend) and Vercel (frontend).
"""
import secrets
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def main():
    viewer_key = f"bcn_vwr_{secrets.token_urlsafe(32)}"
    auditor_key = f"bcn_aud_{secrets.token_urlsafe(32)}"
    admin_key = f"bcn_adm_{secrets.token_urlsafe(32)}"

    print("\n" + "=" * 75)
    print("[*] BEACON PRODUCTION DEPLOYMENT ENVIRONMENT GENERATOR")
    print("=" * 75)
    
    print("\n[1] Generated Cryptographic Bootstrap API Keys:")
    print(f"  * Viewer Key  : {viewer_key}")
    print(f"  * Auditor Key : {auditor_key}")
    print(f"  * Admin Key   : {admin_key}")
    
    print("\n" + "-" * 75)
    print(">> [RENDER BACKEND ENVIRONMENT VARIABLES]")
    print("Copy and paste these into your Render Web Service Environment tab:")
    print("-" * 75)
    render_env = f"""ENVIRONMENT=production
NVIDIA_API_KEY=<your-nvidia-nim-api-key>
LLM_MODEL=meta/llama-3.1-70b-instruct
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-supabase-service-role-or-anon-key>
DATABASE_URL=<your-supabase-database-connection-url>
BOOTSTRAP_VIEWER_API_KEY={viewer_key}
BOOTSTRAP_AUDITOR_API_KEY={auditor_key}
BOOTSTRAP_ADMIN_API_KEY={admin_key}
CORS_ORIGINS=https://<your-vercel-app-name>.vercel.app
BACKEND_CORS_ORIGINS=http://localhost:3000
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
MAX_REQUEST_SIZE_MB=10
AUTH_ENABLED=true
BEACON_AI_ENABLED=true
VECTOR_STORE=chromadb
CHROMA_PERSIST_DIR=/app/chroma_db
LOGS_DIR=/app/logs
MAX_SCAN_GLOBAL_CAP=80
MAX_CONCURRENT_SITE_AUDITS=3
DASHBOARD_DEEP_SCAN_MAX_PAGES=12
DASHBOARD_MAX_SCAN_MAX_PAGES=25"""
    print(render_env)

    print("\n" + "-" * 75)
    print(">> [VERCEL FRONTEND ENVIRONMENT VARIABLES]")
    print("Copy and paste these into your Vercel Project Settings -> Environment Variables:")
    print("-" * 75)
    vercel_env = f"""NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
BEACON_API_URL=https://<your-render-service-name>.onrender.com
BOOTSTRAP_VIEWER_API_KEY={viewer_key}
BOOTSTRAP_AUDITOR_API_KEY={auditor_key}
BOOTSTRAP_ADMIN_API_KEY={admin_key}
NEXT_PUBLIC_ENABLE_AI_FEATURES=true
NEXT_PUBLIC_ENABLE_LIGHTHOUSE_ENRICHMENT=true
NEXT_PUBLIC_ENABLE_REALTIME_UPDATES=true"""
    print(vercel_env)
    
    print("\n" + "=" * 75)
    print("[OK] Note: Ensure matching API keys between Render and Vercel for authentication.")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    main()
