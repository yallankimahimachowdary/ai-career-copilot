#!/usr/bin/env python3
"""
scripts/eval_intent_router.py
-----------------------------
CLI script to evaluate Query Intent Router accuracy, macro-F1, and per-intent metrics.
Outputs a structured summary with dataset provenance.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.intent_router_eval import evaluate_intent_benchmark


async def main():
    parser = argparse.ArgumentParser(description="Evaluate Query Intent Router on labeled benchmark.")
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/evaluation/query_intent_benchmark_v1.json",
        help="Path to labeled benchmark JSON dataset.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to output evaluation report JSON.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use configured LLM provider for intent classification instead of deterministic heuristic.",
    )
    args = parser.parse_args()

    print(f"[INFO] Running Query Intent Router evaluation on: {args.dataset} (use_llm={args.use_llm})")
    report = await evaluate_intent_benchmark(args.dataset, use_llm=args.use_llm)

    summary = report["summary"]
    dataset_meta = report["dataset"]

    print("\n" + "=" * 60)
    print("QUERY INTENT ROUTER EVALUATION REPORT")
    print("=" * 60)
    print(f"Dataset SHA-256 : {dataset_meta['sha256']}")
    print(f"Dataset Version : {dataset_meta['version']}")
    print(f"Total Samples   : {dataset_meta['total_samples']}")
    print(f"Overall Accuracy: {summary['accuracy'] * 100:.2f}% ({summary['correct_count']}/{summary['total_count']})")
    print(f"Macro-F1 Score  : {summary['macro_f1']:.4f}")
    print("-" * 60)
    print(f"{'Intent':<24} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}")
    print("-" * 60)
    for intent, m in report["per_intent"].items():
        print(f"{intent:<24} | {m['precision']:<10.4f} | {m['recall']:<10.4f} | {m['f1_score']:<10.4f} | {m['support']:<8}")
    print("=" * 60 + "\n")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[INFO] Full report written to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
