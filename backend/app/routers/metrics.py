"""
Metrics router — GET /metrics

Retrieves all recorded metrics from metrics_db.json and computes averages.
"""

from fastapi import APIRouter
import json
from pathlib import Path

from typing import Optional

router = APIRouter(tags=["metrics"])
DB_PATH = Path(__file__).parent.parent.parent / "metrics_db.json"

@router.get("/metrics")
async def get_metrics(session_id: Optional[str] = None):
    if not DB_PATH.exists():
        return {"history": [], "averages": {}}
        
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    except Exception:
        return {"history": [], "averages": {}}

    if session_id:
        metrics = [m for m in metrics if m.get("session_id") == session_id]

    if not metrics:
        return {"history": [], "averages": {}}

    avg_ttft = sum(m.get("latency_ttft", 0) for m in metrics) / len(metrics)
    avg_total = sum(m.get("latency_total", 0) for m in metrics) / len(metrics)
    avg_faith = sum(m.get("faithfulness", 0) for m in metrics) / len(metrics)
    avg_relevancy = sum(m.get("answer_relevancy", 0) for m in metrics) / len(metrics)
    avg_context = sum(m.get("context_relevance", 0) for m in metrics) / len(metrics)

    averages = {
        "latency_ttft": avg_ttft,
        "latency_total": avg_total,
        "faithfulness": avg_faith,
        "answer_relevancy": avg_relevancy,
        "context_relevance": avg_context,
    }

    return {"history": metrics, "averages": averages}
