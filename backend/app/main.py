"""
FastAPI application entry point.

Mounts CORS middleware and all API routers.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import upload as upload_router
from app.routers import chat as chat_router
from app.routers import metrics as metrics_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

app = FastAPI(
    title="Document-Based AI Assistant",
    description="Upload documents, ask questions, get cited answers.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}

@app.get("/")
def read_root():
    """Root endpoint for basic health checks by Render."""
    return {"status": "live", "service": "E2M RAG Backend"}


app.include_router(upload_router.router)
app.include_router(chat_router.router)
app.include_router(metrics_router.router)
