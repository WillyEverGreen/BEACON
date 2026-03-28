"""
FastAPI application entry point.
Registers routers, CORS, health check, and ingestion endpoint.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import HealthResponse
from app.routers import rag, audit
from app.services.vector_store import get_chunks_count
from app.services.ingestion import run_full_ingestion
from app.services.vector_store import upsert_chunks, reset_collection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown lifecycle."""
    logger.info("🚀 Accessibility Intelligence Engine starting...")
    logger.info(f"LLM Model: {settings.featherless_model}")
    logger.info(f"Embedding Model: {settings.embedding_model}")
    logger.info(f"Vector Store: {settings.vector_store}")

    chunks_count = get_chunks_count()
    if chunks_count == 0:
        logger.info("📦 Vector store is empty. Run POST /ingest to populate it.")
    else:
        logger.info(f"✅ Vector store has {chunks_count} chunks ready.")

    yield

    logger.info("👋 Accessibility Intelligence Engine shutting down.")


# ── App Setup ──────────────────────────────────────────────────

app = FastAPI(
    title="Accessibility Intelligence Engine",
    description=(
        "Next-gen accessibility auditing API — multi-engine scanning (static + heuristic + "
        "browser probes + axe-core), AI-powered cognitive analysis, confidence scoring, "
        "RAG-backed remediation with WCAG 2.2 + ARIA APG + COGA references. "
        "Surpasses Lighthouse and axe-core in coverage, accuracy, and developer experience."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(rag.router)
app.include_router(audit.router)


# ── Health & Utility Endpoints ─────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        vector_store=settings.vector_store,
        chunks_count=get_chunks_count(),
        llm_model=settings.featherless_model,
    )


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
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Accessibility Intelligence Engine",
        "version": "2.0.0",
        "description": "Next-gen accessibility auditing platform surpassing Lighthouse and axe-core",
        "endpoints": {
            "POST /audit": "Run multi-engine accessibility audit (fast/deep mode)",
            "POST /audit/feedback": "Submit developer feedback for suggested fixes",
            "GET /audit/feedback/stats": "View aggregate feedback statistics",
            "POST /rag": "Query the WCAG knowledge base (explanation + code fix + WCAG ref)",
            "GET /rag/topics": "List available filter topics/levels",
            "POST /ingest": "Ingest WCAG guidelines + repo into vector store",
            "GET /health": "Health check",
        },
        "scan_modes": {
            "fast": "Static HTML + heuristic checks (≤15s)",
            "deep": "Full Playwright + browser probes + axe-core + cognitive analysis (≤120s)",
        },
        "docs": "/docs",
    }
