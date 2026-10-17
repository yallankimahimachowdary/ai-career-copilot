#!/usr/bin/env python3
"""
scripts/eval_rag_grounding.py
-----------------------------
CLI script to evaluate RAG context retrieval and Coach answer grounding against
a benchmark dataset.

Usage:
    python scripts/eval_rag_grounding.py [--dataset data/evaluation/rag_coach_eval_v1.json] [--output artifacts/rag_coach_eval_report.json]
"""

import argparse
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.rag_eval import rag_coach_evaluator


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG and Coach Answer Grounding.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPO_ROOT / "data" / "evaluation" / "rag_coach_eval_v1.json",
        help="Path to JSON benchmark dataset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "artifacts" / "rag_coach_eval_report.json",
        help="Path to output evaluation report JSON.",
    )
    args = parser.parse_args()

    print(f"[RAG EVAL] Loading dataset from: {args.dataset}")
    try:
        report = rag_coach_evaluator.evaluate_benchmark_suite(args.dataset)
    except Exception as exc:
        print(f"[RAG EVAL ERROR] Failed to evaluate benchmark suite: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)

    print("\n==================================================")
    print("           RAG & COACH GROUNDING REPORT           ")
    print("==================================================")
    print(f"Dataset SHA-256:          {report.dataset_sha256[:16]}...")
    print(f"Total Samples Evaluated:  {report.total_samples}")
    print(f"Mean Context Recall:      {report.mean_context_recall * 100:.2f}%")
    print(f"Mean Context Precision:   {report.mean_context_precision * 100:.2f}%")
    print(f"Mean Factual Consistency: {report.mean_factual_consistency * 100:.2f}%")
    print(f"Mean Ref Similarity F1:   {report.mean_reference_similarity_f1 * 100:.2f}%")
    print(f"Hallucination Rate:       {report.hallucination_rate * 100:.2f}%")
    print(f"Grounding Pass Rate:      {report.grounding_pass_rate * 100:.2f}%")
    print(f"Human Review Pending:     {report.human_review_summary.get('pending_review_count', 0)}")
    print(f"Report written to:        {args.output}")
    print("==================================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
