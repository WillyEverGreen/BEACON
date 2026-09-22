"""
FastAPI application entry point.
Registers routers, CORS, health check, and ingestion endpoint.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.core.env_validator import validate_or_exit
from app.db.repository import get_audit_history
from app.models import HealthResponse
from app.observability import (
    configure_logging,
    render_prometheus_metrics,
    trigger_test_alert,
)
from app.routers import audit, dashboard_api, rag
from app.security.auth import APIKeyMiddleware, bootstrap_auth_store
from app.services.audit_runner import get_audit_runtime_health
from app.services.ingestion import run_full_ingestion
from app.services.vector_store import get_chunks_count, reset_collection, upsert_chunks

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown lifecycle."""
    logger.info("=" * 70)
    logger.info("BEACON - Accessibility Intelligence Engine")
    logger.info("=" * 70)
    
    # Validate environment configuration
    validate_or_exit()
    
    logger.info(f"Supabase Project: {settings.supabase_url}")
    logger.info(f"LLM Model: {settings.llm_model}")
    logger.info(f"Embedding Model: {settings.embedding_model}")
    logger.info(f"Vector Store: {settings.vector_store}")
    logger.info(f"Environment: {settings.environment}")

    bootstrap_auth_store()

    # Probe Supabase connectivity to prime the circuit breaker early
    try:
        from app.db.supabase_client import get_supabase, record_supabase_failure, record_supabase_success
        sb = get_supabase()
        _ = sb.table("projects").select("id").limit(1).execute()
        record_supabase_success()
        logger.info("Supabase connection active.")
    except Exception as exc:
        from app.db.supabase_client import record_supabase_failure
        record_supabase_failure()
        logger.info("Supabase unavailable at startup (%s), using local storage fallback.", exc)

    chunks_count = get_chunks_count()
    if chunks_count == 0:
        logger.info("Vector store is empty. Run POST /ingest to populate it.")
    else:
        logger.info(f"Vector store has {chunks_count} chunks ready.")

    yield

    logger.info("Accessibility Intelligence Engine shutting down")


# ── App Setup ───────────────────────────────────────────────────

app = FastAPI(
    title="Accessibility Intelligence Engine",
    description=(
        "Production-grade accessibility auditing API — multi-engine scanning (static + heuristic + "
        "browser probes + axe-core), AI-powered cognitive analysis, confidence scoring, "
        "RAG-backed remediation with WCAG 2.2 + ARIA APG + COGA references. "
        "Features async enrichment, parallel engines, self-learning fix library, "
        "SSE streaming, global backpressure, and fix validation loops."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# ── Middleware Stack (order matters - first added = outermost) ───────

# 1. Error handling middleware (outermost - catches all errors)
from app.middleware.error_handler import error_handler_middleware

app.middleware("http")(error_handler_middleware)

# 2. Security headers (add security headers to all responses)
from app.middleware.security import SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)

# 3. Request size limit (block oversized requests early)
from app.middleware.security import RequestSizeLimitMiddleware

app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=10)

# 4. CORS (configure before other middleware that might block)
from app.middleware.security import configure_cors

configure_cors(app)

# 5. Rate limiting (prevent abuse)
import os

from app.middleware.security import RateLimitMiddleware

rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
if rate_limit_enabled:
    requests_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    requests_per_hour = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour
    )
    logger.info(f"Rate limiting enabled: {requests_per_minute}/min, {requests_per_hour}/hr")
else:
    logger.warning("Rate limiting is DISABLED")

# 6. Request logging (log all requests with timing)
from app.middleware.logging_middleware import RequestLoggingMiddleware

app.add_middleware(RequestLoggingMiddleware)

# 7. Authentication (verify API keys)
if bool(getattr(settings, "auth_enabled", True)):
    app.add_middleware(APIKeyMiddleware)
    logger.info("API key authentication enabled")
else:
    logger.warning("API key authentication is DISABLED")

# Routers
# Canonical versioned API surface.
app.include_router(rag.router, prefix="/v1")
app.include_router(audit.router, prefix="/v1")
app.include_router(dashboard_api.router, prefix="/v1")

# Backward-compatible legacy aliases.
app.include_router(rag.router)
app.include_router(audit.router)
app.include_router(dashboard_api.router)


# ── Health & Utility Endpoints ──────────────────────────────────

@app.get("/v1/config")
async def v1_config():
    """Return safe frontend feature flags for API wiring."""
    return {
        "aiEnabled": bool(getattr(settings, "beacon_ai_enabled", False)),
        "streamEnabled": False,
        "apiVersion": "v1",
        "supabaseUrl": settings.supabase_url,
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        vector_store=settings.vector_store,
        chunks_count=get_chunks_count(),
        llm_model=settings.llm_model,
    )


@app.get("/health/live")
async def health_live():
    """Liveness probe: process is up and serving."""
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe: Supabase + vector store path is available for serving audits."""
    db_ready = True
    db_error = ""
    try:
        from app.db.supabase_client import get_supabase
        sb = get_supabase()
        # Ping Supabase with a simple health touch
        _ = sb.table("audits").select("id").limit(1).execute()
    except Exception as exc:
        db_ready = False
        db_error = str(exc)

    chunks_count = 0
    vector_ready = True
    vector_error = ""
    try:
        chunks_count = int(get_chunks_count())
    except Exception as exc:
        vector_ready = False
        vector_error = str(exc)

    ready = db_ready and vector_ready
    payload = {
        "status": "ready" if ready else "not_ready",
        "db_ready": db_ready,
        "vector_ready": vector_ready,
        "chunks_count": chunks_count,
        "db_error": db_error,
        "vector_error": vector_error,
    }
    if not ready:
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.get("/health/audit")
async def health_audit():
    """Audit runtime probe: backpressure and runtime queue health."""
    runtime = get_audit_runtime_health()
    active = int(runtime.get("active_audits", 0) or 0)
    maximum = max(1, int(runtime.get("max_concurrent_audits", 1) or 1))
    saturation = round(active / maximum, 3)
    status = "healthy"
    if saturation >= 1.0:
        status = "saturated"
    elif saturation >= 0.8:
        status = "high_load"

    return {
        "status": status,
        "saturation": saturation,
        **runtime,
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint():
    """Prometheus metrics from the in-memory sliding telemetry window."""
    payload = render_prometheus_metrics()
    return PlainTextResponse(payload, media_type="text/plain; version=0.0.4")


@app.get("/history")
async def history_endpoint(url: str, limit: int = 20):
    """Return persisted longitudinal score history for a specific URL."""
    return {
        "url": url,
        "history": get_audit_history(url, limit=limit),
    }


@app.post("/test/trigger_alert")
async def trigger_alert_endpoint():
    """Admin utility endpoint to validate outbound alert webhook wiring."""
    return await trigger_test_alert()


@app.post("/ingest")
async def ingest_corpus(reset: bool = False, expand_corpus: bool = False):
    """
    Run corpus ingestion: load WCAG criteria + clone & process repo.
    Set reset=true to wipe and re-index everything.
    Set expand_corpus=true to also scrape all 22 web sources (WCAG, ARIA, COGA, axe, WebAIM, MDN, Regulatory).
    """
    try:
        if reset:
            logger.info("Resetting collection before ingestion...")
            reset_collection()

        chunks = run_full_ingestion(expand_corpus=expand_corpus)

        if not chunks:
            raise HTTPException(status_code=500, detail="Ingestion produced no chunks.")

        count = upsert_chunks(chunks)

        return {
            "status": "success",
            "chunks_ingested": count,
            "total_chunks": get_chunks_count(),
            "message": f"Successfully ingested {count} chunks into vector store.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e!s}")


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Accessibility Intelligence Engine",
        "version": "3.0.0",
        "schema_version": getattr(settings, "schema_version", "3.1"),
        "description": "Production-grade accessibility auditing platform with async RAG, parallel engines, self-learning fix library, and SSE streaming",
        "endpoints": {
            "POST /audit": "Run multi-engine accessibility audit (fast/deep mode)",
            "POST /audit/stream": "SSE streaming audit with real-time progress events",
            "GET /audit/enrichment/{id}": "Poll for background RAG enrichment results",
            "POST /audit/feedback": "Submit developer feedback for suggested fixes",
            "GET /audit/feedback/stats": "View aggregate feedback statistics",
            "GET /audit/cache/stats": "Fix Library and Page Cache telemetry",
            "POST /rag": "Query the WCAG knowledge base (explanation + code fix + WCAG ref)",
            "GET /rag/topics": "List available filter topics/levels",
            "POST /ingest": "Ingest WCAG guidelines + repo into vector store",
            "GET /health": "Health check",
        },
        "scan_modes": {
            "fast": "Static HTML + heuristic checks (â‰¤15s)",
            "deep": "Full Playwright + browser probes + axe-core + cognitive analysis (â‰¤120s)",
            "max": "Extended exploration mode with broader coverage budget",
        },
        "optimization_features": [
            "Async RAG enrichment (non-blocking)",
            "Parallel check engines (asyncio.gather)",
            "Playwright circuit breaker (semaphore + timeout)",
            "Global backpressure guard (auto-degrade at >20 concurrent)",
            "LLM call batching (group by WCAG criterion)",
            "Self-learning Fix Library (85% success gate)",
            "Fix validation loop (rule-specific validators)",
            "Page-level + DOM-structure caching (24h TTL)",
            "SSE streaming for real-time progress",
            "TTFI telemetry tracking",
        ],
        "docs": "/docs",
    }
# AI Layer Stabilization v2

