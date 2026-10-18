"""Script to execute Smoke Run v3 for LangGraph Orchestrator against live services.

Executes all 5 intents twice against live Ollama, Postgres, and Neo4j,
verifying that every intent achieves status 'success' with 0 unrecovered errors.
Outputs results to results/graph_smoke_run_v3.json.
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))

from app.db.session import AsyncSessionLocal
from app.schemas.chat import ChatQueryRequest
from app.services.graph_orchestrator import langgraph_orchestrator

QUERIES = [
    {
        "intent": "JOB_SEARCH",
        "query": "What Python backend developer jobs are open in San Francisco?",
    },
    {
        "intent": "SKILL_GAP_ANALYSIS",
        "query": "What skills do I need to learn to transition to a DevOps Engineer?",
    },
    {
        "intent": "INTERVIEW_PREPARATION",
        "query": "Can you give me practice behavioral interview questions for a senior role?",
    },
    {
        "intent": "CAREER_ADVICE",
        "query": "What is the median salary and hiring outlook for Machine Learning Engineers?",
    },
    {
        "intent": "RESUME_FEEDBACK",
        "query": "How can I optimize my resume bullet points for software engineering?",
    },
]


async def run_single_intent(item: Dict[str, str], iteration: int) -> Dict[str, Any]:
    print(f"\n--- [Iteration {iteration}] Executing Intent: {item['intent']} ---")
    print(f"Query: {item['query']}")
    t0 = time.perf_counter()

    async with AsyncSessionLocal() as session:
        req = ChatQueryRequest(query=item["query"])
        resp = await langgraph_orchestrator.execute(req, db=session, use_llm=True)

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    # Extract orchestrator trace from sources
    trace = next((s for s in resp.sources if s.get("type") == "orchestrator_trace"), {})
    status = trace.get("status", "unknown")
    completed_nodes = trace.get("completed_nodes", [])
    node_timings_ms = trace.get("node_timings_ms", {})
    retries = trace.get("retries", {})
    errors = trace.get("errors", [])

    print(f"Result Status: {status}")
    print(f"Completed Nodes: {completed_nodes}")
    print(f"Elapsed: {elapsed_ms}ms")
    if errors:
        print(f"Errors encountered: {errors}")

    return {
        "intent": item["intent"],
        "query": item["query"],
        "status": status,
        "classified_intent": resp.router_decision.intent.value,
        "confidence": resp.router_decision.confidence,
        "backend": resp.router_decision.backend,
        "completed_nodes": completed_nodes,
        "node_timings_ms": node_timings_ms,
        "retries": retries,
        "errors": errors,
        "total_latency_ms": elapsed_ms,
        "has_real_content": len(resp.response) > 50,
        "response_char_count": len(resp.response),
        "sources_count": len(resp.sources),
        "recommendations_count": len(resp.actionable_recommendations),
    }


async def main():
    print("=================================================================")
    print("Starting Smoke Run v3: 5 Intents x 2 Iterations against Live Services")
    print("=================================================================")

    # Run 1
    print("\n>>> STARTING PASS 1 OF 2 <<<")
    pass_1_results = []
    for item in QUERIES:
        res = await run_single_intent(item, iteration=1)
        pass_1_results.append(res)

    # Run 2
    print("\n>>> STARTING PASS 2 OF 2 <<<")
    pass_2_results = []
    for item in QUERIES:
        res = await run_single_intent(item, iteration=2)
        pass_2_results.append(res)

    # Verify both passes
    print("\n=================================================================")
    print("VERIFICATION OF BOTH PASSES:")
    all_passed = True
    v3_summary = []

    for idx, item in enumerate(QUERIES):
        p1 = pass_1_results[idx]
        p2 = pass_2_results[idx]
        intent = item["intent"]

        p1_ok = (p1["status"] == "success" and len(p1["errors"]) == 0)
        p2_ok = (p2["status"] == "success" and len(p2["errors"]) == 0)

        print(f"Intent {intent}: Pass 1 -> {p1['status']} (errors={len(p1['errors'])}), Pass 2 -> {p2['status']} (errors={len(p2['errors'])})")
        if not (p1_ok and p2_ok):
            all_passed = False

        combined_entry = {
            "intent": intent,
            "query": item["query"],
            "status": "success" if (p1_ok and p2_ok) else f"p1:{p1['status']}|p2:{p2['status']}",
            "classified_intent": p2["classified_intent"],
            "confidence": p2["confidence"],
            "backend": p2["backend"],
            "completed_nodes": p2["completed_nodes"],
            "node_timings_ms": p2["node_timings_ms"],
            "retries": p2["retries"],
            "errors": p2["errors"],
            "total_latency_ms": p2["total_latency_ms"],
            "has_real_content": p2["has_real_content"],
            "response_char_count": p2["response_char_count"],
            "sources_count": p2["sources_count"],
            "recommendations_count": p2["recommendations_count"],
            "iterations_verified": 2,
            "pass_1_status": p1["status"],
            "pass_2_status": p2["status"],
        }
        v3_summary.append(combined_entry)

    out_path = os.path.join("results", "graph_smoke_run_v3.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(v3_summary, f, indent=2)

    print(f"\nSaved Smoke Run v3 results to {out_path}")
    print(f"Overall Success: {all_passed}")

    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
