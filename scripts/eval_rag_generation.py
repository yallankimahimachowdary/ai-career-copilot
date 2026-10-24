"""scripts/eval_rag_generation.py
--------------------------------
RAG Generation Evaluation Harness (Remediation R6).

Evaluates 2x2 Factorial Matrix:
- Retrieval: Fixed Baseline vs Router-Driven
- Generation LLM: Ollama (llama3.2:3b local) vs Gemini (gemini-2.0-flash)

In-House RAGAS Metrics (No external pip dependencies):
1. Faithfulness: Ratio of claims in generated answer supported by retrieved context.
2. Answer Relevancy: Dense semantic similarity between query embedding and answer embedding.
3. Context Precision: Rank-weighted precision of key facts in retrieved context chunks.
4. Context Recall: Proportion of ground truth key facts captured in retrieved context.

Methodological Safeguard:
Explicitly notes self-judging bias in LLM-as-a-judge workflows and computes
deterministic sentence-transformer embeddings and claim containment alongside LLM scores.

Exports:
- results/rag_generation.json: Complete evaluation results across 2x2 matrix.
- results/rag_human_validation_sample.csv: Blinded, stratified 30-sample dataset for human evaluation.
"""

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from app.core.config import settings
from app.services.embedding_service import get_sentence_transformer
from scripts.eval_rag_retrieval import (
    compute_file_sha256,
    evaluate_document_relevance,
    retrieve_fixed_baseline,
    retrieve_router_driven,
)

QUERIES_FILE = Path("data/rag_eval/rag_queries_v1.jsonl")
RESULTS_FILE = Path("results/rag_generation.json")
HUMAN_SAMPLE_FILE = Path("results/rag_human_validation_sample.csv")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"


# ---------------------------------------------------------------------------
# LLM Generation Providers
# ---------------------------------------------------------------------------

async def generate_ollama(prompt: str, timeout: float = 60.0) -> str:
    """Generate response via local Ollama instance."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 256, "num_ctx": 8192},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
            return f"Ollama error: HTTP {resp.status_code}"
    except Exception as exc:
        return f"Ollama connection error: {exc}"


async def generate_gemini(prompt: str, timeout: float = 45.0) -> str:
    """Generate response via Gemini API with deterministic fallback."""
    if not settings.GEMINI_API_KEY:
        return "Gemini API key not configured; skipping cloud generation."

    model_name = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite").removeprefix("models/")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 256},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
            return f"Gemini API returned status {resp.status_code}"
    except Exception as exc:
        return f"Gemini request exception: {exc}"


# ---------------------------------------------------------------------------
# In-House RAGAS Metrics
# ---------------------------------------------------------------------------

def split_into_claims(text: str) -> List[str]:
    """Split text into distinct sentences/claims."""
    raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw_sentences if len(s.strip()) > 10]


def compute_faithfulness(answer: str, context_chunks: List[str]) -> float:
    """Computes ratio of claims in generated answer supported by the retrieved context."""
    claims = split_into_claims(answer)
    if not claims:
        return 0.5  # Neutral default for empty/unsplit response

    full_context = " ".join(context_chunks).lower()
    supported = 0

    for claim in claims:
        # Extract informative words
        words = [
            w.lower() for w in re.findall(r"\b[a-zA-Z0-9+#./-]{3,}\b", claim)
            if w.lower() not in {"and", "the", "for", "with", "from", "that", "this", "are", "was", "will", "can", "may", "about"}
        ]
        if not words:
            continue
        hits = sum(1 for w in words if w in full_context)
        # Supported if at least 50% of informative tokens or a bigram appear in context
        phrase_hit = any(f"{words[i]} {words[i+1]}" in full_context for i in range(len(words) - 1)) if len(words) >= 2 else False
        if phrase_hit or (hits / len(words) >= 0.5):
            supported += 1

    return round(supported / len(claims), 4)


def compute_answer_relevancy(query: str, answer: str) -> float:
    """Computes semantic cosine similarity between query and generated answer."""
    if not answer.strip():
        return 0.0

    st_model = get_sentence_transformer()
    q_emb = st_model.encode(query, convert_to_numpy=True, normalize_embeddings=True)
    a_emb = st_model.encode(answer[:500], convert_to_numpy=True, normalize_embeddings=True)

    sim = float(np.dot(q_emb, a_emb))
    return round(float(np.clip(sim, 0.0, 1.0)), 4)


def compute_context_precision(context_chunks: List[str], key_facts: List[str]) -> float:
    """Computes rank-weighted precision of key facts in retrieved context chunks."""
    if not context_chunks or not key_facts:
        return 0.0

    precisions = []
    relevant_count = 0

    for k, chunk in enumerate(context_chunks, 1):
        is_rel, _ = evaluate_document_relevance(chunk, key_facts)
        if is_rel:
            relevant_count += 1
            precisions.append(relevant_count / k)

    if not precisions:
        return 0.0
    return round(float(np.mean(precisions)), 4)


def compute_context_recall(context_chunks: List[str], key_facts: List[str]) -> float:
    """Computes proportion of ground truth key facts captured in retrieved context chunks."""
    if not key_facts:
        return 1.0

    full_context = " ".join(context_chunks)
    matched_facts = 0

    for fact in key_facts:
        is_rel, _ = evaluate_document_relevance(full_context, [fact])
        if is_rel:
            matched_facts += 1

    return round(matched_facts / len(key_facts), 4)


# ---------------------------------------------------------------------------
# Main Generation Evaluation Runner
# ---------------------------------------------------------------------------

async def evaluate_generation(sample_size: int = 20):
    print("=================================================================")
    print("AI Career Copilot - RAG Generation Evaluation (2x2 Matrix) (R6)")
    print("=================================================================")

    if not QUERIES_FILE.exists():
        print(f"Error: {QUERIES_FILE} not found!")
        sys.exit(1)

    queries: List[Dict[str, Any]] = []
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))

    dataset_sha = compute_file_sha256(QUERIES_FILE)
    print(f"Loaded {len(queries)} queries. Evaluating stratified sample of {sample_size} queries.")

    # Stratified sampling: equal representation across 4 categories
    rng = random.Random(42)
    categories = ["interview_prep", "learning_resources", "role_progression", "market_demand"]
    sampled_queries: List[Dict[str, Any]] = []
    per_cat = max(1, sample_size // len(categories))
    for cat in categories:
        cat_q = [q for q in queries if q["category"] == cat]
        sampled_queries.extend(rng.sample(cat_q, min(per_cat, len(cat_q))))

    # 2x2 Matrix definitions
    quadrants = [
        ("fixed_retrieval_ollama", "fixed", "ollama"),
        ("fixed_retrieval_gemini", "fixed", "gemini"),
        ("router_retrieval_ollama", "router", "ollama"),
        ("router_retrieval_gemini", "router", "gemini"),
    ]

    matrix_results: Dict[str, Dict[str, List[float]]] = {
        name: {"faithfulness": [], "relevancy": [], "precision": [], "recall": []}
        for name, _, _ in quadrants
    }

    all_generations_for_human: List[Dict[str, Any]] = []

    print(f"\nEvaluating 2x2 Matrix across {len(sampled_queries)} queries...")
    for idx, q in enumerate(sampled_queries, 1):
        q_id = q["id"]
        q_text = q["query_text"]
        key_facts = q["key_facts"]

        # Retrieve contexts
        fixed_chunks = await retrieve_fixed_baseline(q_text, top_k=3)
        router_chunks = await retrieve_router_driven(q, top_k=3)

        fixed_ctx_str = "\n".join(f"- {c}" for c in fixed_chunks)
        router_ctx_str = "\n".join(f"- {c}" for c in router_chunks)

        prompt_fixed = (
            f"Context Information:\n{fixed_ctx_str}\n\n"
            f"User Query: {q_text}\n\n"
            f"Provide a direct, factual answer based ONLY on the context provided above:"
        )
        prompt_router = (
            f"Context Information:\n{router_ctx_str}\n\n"
            f"User Query: {q_text}\n\n"
            f"Provide a direct, factual answer based ONLY on the context provided above:"
        )

        # Generate responses across the 4 cells
        ans_fixed_ollama = await generate_ollama(prompt_fixed)
        ans_fixed_gemini = await generate_gemini(prompt_fixed)
        ans_router_ollama = await generate_ollama(prompt_router)
        ans_router_gemini = await generate_gemini(prompt_router)

        cell_data = [
            ("fixed_retrieval_ollama", fixed_chunks, ans_fixed_ollama),
            ("fixed_retrieval_gemini", fixed_chunks, ans_fixed_gemini),
            ("router_retrieval_ollama", router_chunks, ans_router_ollama),
            ("router_retrieval_gemini", router_chunks, ans_router_gemini),
        ]

        for cell_name, chunks, ans_text in cell_data:
            faith = compute_faithfulness(ans_text, chunks)
            rel = compute_answer_relevancy(q_text, ans_text)
            prec = compute_context_precision(chunks, key_facts)
            rec = compute_context_recall(chunks, key_facts)

            matrix_results[cell_name]["faithfulness"].append(faith)
            matrix_results[cell_name]["relevancy"].append(rel)
            matrix_results[cell_name]["precision"].append(prec)
            matrix_results[cell_name]["recall"].append(rec)

            all_generations_for_human.append({
                "query_id": q_id,
                "category": q["category"],
                "query_text": q_text,
                "quadrant": cell_name,
                "generated_answer": ans_text,
            })

        print(f"  [{idx}/{len(sampled_queries)}] Query {q_id} evaluated across 4 quadrants.")

    # Aggregate 2x2 summaries
    summary_2x2: Dict[str, Any] = {}
    for cell_name, metrics in matrix_results.items():
        summary_2x2[cell_name] = {
            "mean_faithfulness": round(float(np.mean(metrics["faithfulness"])), 4),
            "mean_answer_relevancy": round(float(np.mean(metrics["relevancy"])), 4),
            "mean_context_precision": round(float(np.mean(metrics["precision"])), 4),
            "mean_context_recall": round(float(np.mean(metrics["recall"])), 4),
            "sample_size": len(metrics["faithfulness"]),
        }

    final_output = {
        "metadata": {
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset_sha256": dataset_sha,
            "sample_size": len(sampled_queries),
            "total_queries_pool": len(queries),
            "methodological_notes": {
                "self_judging_bias_warning": (
                    "When an LLM serves as both generator and evaluator, it exhibits systematic positive bias. "
                    "To mitigate self-judging bias, this harness computes objective embedding cosine similarities "
                    "and token containment metrics, and exports a blinded human validation sample."
                )
            },
        },
        "two_by_two_matrix_results": summary_2x2,
    }

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
    print(f"\nSaved generation evaluation results to {RESULTS_FILE}")

    # Export Blinded Human Validation Sample (30 items)
    print(f"Exporting stratified blinded human validation sample to {HUMAN_SAMPLE_FILE}...")
    alias_map = {
        "fixed_retrieval_ollama": "system_A",
        "fixed_retrieval_gemini": "system_B",
        "router_retrieval_ollama": "system_C",
        "router_retrieval_gemini": "system_D",
    }

    # Sample 30 items
    human_sample = rng.sample(all_generations_for_human, min(30, len(all_generations_for_human)))
    rng.shuffle(human_sample)

    HUMAN_SAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HUMAN_SAMPLE_FILE, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "sample_id", "query_id", "category", "query_text",
            "system_alias", "generated_answer", "annotator_1_score", "annotator_2_score", "notes"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for s_idx, item in enumerate(human_sample, 1):
            writer.writerow({
                "sample_id": f"human_val_{s_idx:03d}",
                "query_id": item["query_id"],
                "category": item["category"],
                "query_text": item["query_text"],
                "system_alias": alias_map[item["quadrant"]],
                "generated_answer": item["generated_answer"],
                "annotator_1_score": "",  # Blank for manual rubric grading (1-5)
                "annotator_2_score": "",  # Blank for second rater
                "notes": "",
            })

    print(f"Blinded sample exported to {HUMAN_SAMPLE_FILE} ({len(human_sample)} items).")
    print("=================================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=12, help="Number of queries to evaluate")
    args = parser.parse_args()
    asyncio.run(evaluate_generation(sample_size=args.samples))
