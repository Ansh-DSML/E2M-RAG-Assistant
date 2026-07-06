"""
Background evaluator using LLM-as-a-judge to compute reference-free RAG metrics.
Calculates Faithfulness, Answer Relevancy, and Context Relevance.
Also logs Time to First Token (TTFT) and Total Latency.
Writes results to metrics_db.json.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional
from pathlib import Path

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langsmith import traceable

from app.config import settings

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "metrics_db.json"


def _load_metrics() -> list[dict]:
    if not DB_PATH.exists():
        return []
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def _save_metric(metric: dict):
    metrics = _load_metrics()
    metrics.append(metric)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


@traceable(name="Evaluate Faithfulness")
def evaluate_faithfulness(question: str, context: str, answer: str, llm: ChatGroq) -> float:
    prompt = f"""You are an impartial judge. Evaluate if the following ANSWER is entirely faithful to the provided CONTEXT.
If the ANSWER contains ANY claims, facts, or figures that are NOT present in the CONTEXT, score it 0.
If the ANSWER is entirely derived from the CONTEXT, score it 1.
If it is partially faithful, score it between 0 and 1.
Respond ONLY with a single float number between 0.0 and 1.0.

CONTEXT:
{context}

ANSWER:
{answer}

SCORE:"""
    response = llm.invoke(prompt)
    try:
        return float(response.content.strip())
    except:
        return 0.0


@traceable(name="Evaluate Answer Relevancy")
def evaluate_answer_relevancy(question: str, answer: str, llm: ChatGroq) -> float:
    prompt = f"""You are an impartial judge. Evaluate if the following ANSWER directly addresses the user's QUESTION.
If the ANSWER completely and directly answers the QUESTION, score it 1.
If the ANSWER is evasive, completely off-topic, or fails to answer the question, score it 0.
If it partially answers it, score between 0 and 1.
Respond ONLY with a single float number between 0.0 and 1.0.

QUESTION:
{question}

ANSWER:
{answer}

SCORE:"""
    response = llm.invoke(prompt)
    try:
        return float(response.content.strip())
    except:
        return 0.0


@traceable(name="Evaluate Context Relevance")
def evaluate_context_relevance(question: str, context: str, llm: ChatGroq) -> float:
    prompt = f"""You are an impartial judge. Evaluate if the following CONTEXT contains useful information to answer the user's QUESTION.
If the CONTEXT contains the exact answer, score it 1.
If the CONTEXT is completely irrelevant noise, score it 0.
Respond ONLY with a single float number between 0.0 and 1.0.

QUESTION:
{question}

CONTEXT:
{context}

SCORE:"""
    response = llm.invoke(prompt)
    try:
        return float(response.content.strip())
    except:
        return 0.0


@traceable(name="RAG Interaction Evaluation")
def run_evaluation(
    question: str,
    context: str,
    answer: str,
    latency_ttft: float,
    latency_total: float,
    session_id: str = "default",
):
    """Run all evaluations asynchronously and save to db."""
    logger.info("Starting background metrics evaluation for question: %s", question[:50])
    
    try:
        llm_judge = ChatGroq(
            api_key=settings.groq_api_key_judge,
            model=settings.groq_model,
            temperature=0.0,
            max_tokens=10,
        )

        faithfulness = evaluate_faithfulness(question, context, answer, llm_judge)
        answer_relevancy = evaluate_answer_relevancy(question, answer, llm_judge)
        context_relevance = evaluate_context_relevance(question, context, llm_judge)

        record = {
            "timestamp": time.time(),
            "question": question,
            "answer_preview": answer[:100] + "..." if len(answer) > 100 else answer,
            "latency_ttft": latency_ttft,
            "latency_total": latency_total,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_relevance": context_relevance,
            "session_id": session_id,
        }
        
        _save_metric(record)
        logger.info("Evaluation complete. Scores saved.")
    except Exception as e:
        logger.error("Error during evaluation: %s", e)
