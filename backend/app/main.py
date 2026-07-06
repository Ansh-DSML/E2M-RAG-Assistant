"""
FastAPI application entry point.

STAGE 1 — app instance, CORS middleware, health-check route.
Routers for /upload and /chat will be mounted in later stages.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import upload as upload_router

# ── App instance ────────────────────────────────────────────────

app = FastAPI(
    title="Document-Based AI Assistant",
    description="Upload documents, ask questions, get cited answers.",
    version="0.1.0",
)

# ── CORS ────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health check ────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Simple liveness probe — confirms the backend is up."""
    return {"status": "ok"}

# ── Routers ─────────────────────────────────────────────────────

app.include_router(upload_router.router)
