#!/usr/bin/env python3
"""
scripts/eval_intent_router.py
-----------------------------
CLI script to evaluate Query Intent Router backends:
  - trained (scikit-learn TF-IDF + LogisticRegression)
  - heuristic (deterministic regex rules)
  - llm (zero-shot Ollama / Llama)

Includes:
  - Hash locking check before reading test split
  - Macro-F1, per-class Precision/Recall/F1, confusion matrix
  - 95% bootstrap confidence intervals (1,000 resamples, percentile method)
  - Query latency profiling (mean, p95)
  - McNemar's test comparing trained vs heuristic
  - Separate reporting for hard cases (secondary_intent is not null)
  - Legacy v1 benchmark evaluation (clearly marked as 'development set')
  - Append-only test run audit logging to results/router_test_runs.jsonl
"""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
import scipy.stats
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.chat import IntentType, RouterDecision
from app.services.intent_router_eval import to_canonical_intent
from app.services.router_service import router_service


ALL_INTENTS = [
    "job_search",
    "skill_gap_analysis",
    "resume_feedback",
    "career_advice",
    "interview_preparation",
]


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        h.update(f.read())
    return h.hexdigest().upper()


def get_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    except Exception:
        return "UNKNOWN"


def load_split_with_hash_check(split_name: str, data_dir: Path = Path("data/router")) -> Tuple[List[dict], str]:
    split_file = data_dir / f"{split_name}.jsonl"
    metadata_file = data_dir / "metadata.json"

    if not split_file.exists():
        raise FileNotFoundError(f"Split file not found: {split_file}")

    actual_hash = compute_sha256(split_file)

    if split_name == "test" and metadata_file.exists():
        with open(metadata_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        expected_hash = meta.get("splits", {}).get("test", {}).get("sha256", "").upper()
        if expected_hash and actual_hash != expected_hash:
            raise ValueError(
                f"[SECURITY ALERT] Test set hash mismatch!\n"
                f"  Expected locked hash: {expected_hash}\n"
                f"  Actual file hash:    {actual_hash}\n"
                f"Evaluation aborted to prevent evaluating tampered or modified test data."
            )
        print(f"[VERIFIED] Test split SHA-256 matches locked hash: {actual_hash}")
    else:
        print(f"[INFO] Loaded split '{split_name}' (SHA-256: {actual_hash})")

    items = []
    with open(split_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items, actual_hash


def compute_bootstrap_ci(y_true: np.ndarray, y_pred: np.ndarray, n_bootstraps: int = 1000, seed: int = 42) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    boot_accs = []
    for _ in range(n_bootstraps):
        indices = rng.integers(0, n, size=n)
        acc = float(accuracy_score(y_true[indices], y_pred[indices]))
        boot_accs.append(acc)
    ci_lower = float(np.percentile(boot_accs, 2.5))
    ci_upper = float(np.percentile(boot_accs, 97.5))
    return ci_lower, ci_upper


def compute_mcnemar_test(
    y_true: List[str],
    preds_trained: List[str],
    preds_heuristic: List[str],
) -> Dict[str, Any]:
    n11 = 0  # both correct
    n10 = 0  # trained correct, heuristic wrong
    n01 = 0  # trained wrong, heuristic correct
    n00 = 0  # both wrong

    for yt, pt, ph in zip(y_true, preds_trained, preds_heuristic):
        corr_trained = (pt == yt)
        corr_heuristic = (ph == yt)
        if corr_trained and corr_heuristic:
            n11 += 1
        elif corr_trained and not corr_heuristic:
            n10 += 1
        elif not corr_trained and corr_heuristic:
            n01 += 1
        else:
            n00 += 1

    contingency = {
        "n_both_correct": n11,
        "n_trained_correct_heuristic_wrong": n10,
        "n_heuristic_correct_trained_wrong": n01,
        "n_both_wrong": n00,
        "table": [[n11, n10], [n01, n00]],
    }

    discordant = n10 + n01
    if discordant == 0:
        chi2 = 0.0
        p_val = 1.0
    else:
        # Edwards continuity correction
        chi2 = float((abs(n10 - n01) - 1.0) ** 2 / discordant)
        p_val = float(scipy.stats.chi2.sf(chi2, df=1))

    return {
        "contingency_table": contingency,
        "discordant_pairs": discordant,
        "statistic": round(chi2, 4),
        "p_value": float(p_val),
        "significant_at_05": bool(p_val < 0.05),
    }


async def evaluate_backend(
    backend: str,
    items: List[dict],
    seed: int = 42,
) -> Optional[Dict[str, Any]]:
    print(f"\n--- Evaluating Backend: {backend} ({len(items)} samples) ---")

    if backend == "llm":
        # Check if Ollama is reachable
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get("http://localhost:11434")
        except Exception:
            print("[WARNING] Ollama unreachable - evaluation skipped")
            return None

    y_true: List[str] = []
    y_pred: List[str] = []
    confidences: List[float] = []
    latencies: List[float] = []
    per_item_records: List[Dict[str, Any]] = []

    for item in items:
        query = item["query"]
        ground_truth = to_canonical_intent(item.get("intent") or item.get("ground_truth_intent"))

        start_time = time.perf_counter()
        if backend == "trained":
            decision = await router_service.classify_intent(query, backend="trained")
        elif backend == "heuristic":
            decision = await router_service.classify_intent(query, backend="heuristic")
        elif backend == "llm":
            decision = await router_service.classify_intent(query, backend="llm", use_llm=True)
        else:
            raise ValueError(f"Unknown backend: {backend}")
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        predicted = to_canonical_intent(decision.intent)
        conf = float(decision.confidence)

        y_true.append(ground_truth)
        y_pred.append(predicted)
        confidences.append(conf)
        latencies.append(latency_ms)

        per_item_records.append({
            "id": item.get("id"),
            "query": query,
            "ground_truth": ground_truth,
            "predicted": predicted,
            "is_correct": ground_truth == predicted,
            "confidence": conf,
            "secondary_intent": item.get("secondary_intent"),
            "latency_ms": latency_ms,
        })

    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)

    acc = float(accuracy_score(y_true_arr, y_pred_arr))
    macro_f1 = float(f1_score(y_true_arr, y_pred_arr, average="macro", labels=ALL_INTENTS, zero_division=0))
    ci_lower, ci_upper = compute_bootstrap_ci(y_true_arr, y_pred_arr, n_bootstraps=1000, seed=seed)

    cm = confusion_matrix(y_true_arr, y_pred_arr, labels=ALL_INTENTS)
    cm_dict = {
        "classes": ALL_INTENTS,
        "matrix": cm.tolist(),
    }

    per_class = {}
    for cls in ALL_INTENTS:
        cls_mask_true = (y_true_arr == cls)
        cls_mask_pred = (y_pred_arr == cls)
        p = float(precision_score(cls_mask_true, cls_mask_pred, zero_division=0))
        r = float(recall_score(cls_mask_true, cls_mask_pred, zero_division=0))
        f1 = float(f1_score(cls_mask_true, cls_mask_pred, zero_division=0))
        sup = int(np.sum(cls_mask_true))
        per_class[cls] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1_score": round(f1, 4),
            "support": sup,
        }

    # Latency stats
    lat_mean = float(np.mean(latencies))
    lat_p95 = float(np.percentile(latencies, 95))

    # Hard cases metrics
    hard_indices = [i for i, it in enumerate(items) if it.get("secondary_intent") is not None]
    if hard_indices:
        hard_y_true = y_true_arr[hard_indices]
        hard_y_pred = y_pred_arr[hard_indices]
        hard_acc = float(accuracy_score(hard_y_true, hard_y_pred))
        hard_f1 = float(f1_score(hard_y_true, hard_y_pred, average="macro", zero_division=0))
    else:
        hard_acc = 0.0
        hard_f1 = 0.0

    print(f"Accuracy:         {acc * 100:.2f}% (95% CI: [{ci_lower * 100:.2f}%, {ci_upper * 100:.2f}%])")
    print(f"Macro-F1:         {macro_f1:.4f}")
    print(f"Hard Cases Acc:   {hard_acc * 100:.2f}% ({len(hard_indices)} items)")
    print(f"Mean Latency:     {lat_mean:.2f} ms (p95: {lat_p95:.2f} ms)")

    return {
        "backend": backend,
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "ci_95": [round(ci_lower, 4), round(ci_upper, 4)],
        "latency_ms_mean": round(lat_mean, 2),
        "latency_ms_p95": round(lat_p95, 2),
        "per_class": per_class,
        "confusion_matrix": cm_dict,
        "hard_cases": {
            "count": len(hard_indices),
            "accuracy": round(hard_acc, 4),
            "macro_f1": round(hard_f1, 4),
        },
        "predictions": y_pred,
        "per_item_results": per_item_records,
    }


async def evaluate_legacy_benchmark(backend: str = "trained") -> Dict[str, Any]:
    legacy_file = Path("data/evaluation/query_intent_benchmark_v1.json")
    if not legacy_file.exists():
        return {"status": "missing"}

    with open(legacy_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    samples = data.get("samples", [])
    if not samples:
        return {"status": "empty"}

    y_true = []
    y_pred = []
    for it in samples:
        yt = to_canonical_intent(it["ground_truth_intent"])
        dec = await router_service.classify_intent(it["query"], backend=backend)
        yp = to_canonical_intent(dec.intent)
        y_true.append(yt)
        y_pred.append(yp)

    acc = float(accuracy_score(y_true, y_pred))
    f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    return {
        "dataset_name": "query_intent_benchmark_v1.json",
        "description": "Historical development set (50 queries, appended to train split)",
        "total_samples": len(samples),
        "backend": backend,
        "accuracy": round(acc, 4),
        "macro_f1": round(f1, 4),
    }


def append_audit_run(
    log_path: Path,
    git_commit: str,
    model_name: str,
    split_name: str,
    split_sha: str,
    accuracy: float,
    macro_f1: float,
    latency_ms_mean: float,
    tau: float,
    coverage: float,
):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "model_name": model_name,
        "split": split_name,
        "split_sha256": split_sha,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "tau": tau,
        "coverage": coverage,
        "latency_ms_mean": latency_ms_mean,
        "user_or_agent_tag": "remediation_r3_agent",
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[AUDIT LOGGED] Appended test run for '{model_name}' to {log_path}")


async def main():
    parser = argparse.ArgumentParser(description="Evaluate Intent Router Backends")
    parser.add_argument("--model", type=str, choices=["trained", "heuristic", "llm", "all"], default="all")
    parser.add_argument("--split", type=str, choices=["dev", "test"], default="test")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("results/router_eval_v1.json"))
    parser.add_argument("--runs-log", type=Path, default=Path("results/router_test_runs.jsonl"))
    args = parser.parse_args()

    git_commit = get_git_commit()
    print("=================================================================")
    print("AI Career Copilot - Query Intent Router Evaluation Suite")
    print("=================================================================")
    print(f"Git Commit:   {git_commit}")
    print(f"Target Split: {args.split}")
    print(f"Model(s):     {args.model}")
    print(f"Random Seed:  {args.seed}")

    items, split_sha256 = load_split_with_hash_check(args.split)
    models_to_eval = ["trained", "heuristic", "llm"] if args.model == "all" else [args.model]

    results: Dict[str, Any] = {}
    preds: Dict[str, List[str]] = {}

    for m in models_to_eval:
        res = await evaluate_backend(m, items, seed=args.seed)
        if res is not None:
            results[m] = res
            preds[m] = res["predictions"]
        else:
            results[m] = {
                "backend": m,
                "status": "not run",
                "message": "Ollama unreachable - evaluation skipped",
            }

    # McNemar's test if both trained and heuristic were evaluated
    mcnemar_res = None
    if "trained" in preds and "heuristic" in preds:
        y_true = [to_canonical_intent(it.get("intent") or it.get("ground_truth_intent")) for it in items]
        mcnemar_res = compute_mcnemar_test(y_true, preds["trained"], preds["heuristic"])
        print("\n=================================================================")
        print("MCNEMAR'S TEST: Trained vs Heuristic")
        print("=================================================================")
        ct = mcnemar_res["contingency_table"]
        print(f"  Both Correct:                     {ct['n_both_correct']}")
        print(f"  Trained Correct, Heuristic Wrong: {ct['n_trained_correct_heuristic_wrong']}")
        print(f"  Heuristic Correct, Trained Wrong: {ct['n_heuristic_correct_trained_wrong']}")
        print(f"  Both Wrong:                       {ct['n_both_wrong']}")
        print(f"  Discordant Pairs:                 {mcnemar_res['discordant_pairs']}")
        print(f"  Chi-squared (with correction):    {mcnemar_res['statistic']}")
        print(f"  p-value (two-sided):              {mcnemar_res['p_value']:.4e}")
        print(f"  Statistically Significant:        {mcnemar_res['significant_at_05']}")

    # Legacy Benchmark evaluation (development set)
    legacy_res = await evaluate_legacy_benchmark("trained")
    legacy_heur = await evaluate_legacy_benchmark("heuristic")

    # Majority baseline
    majority_acc = 1.0 / len(ALL_INTENTS)  # 20.0%

    # Retrieve tau & coverage from model metadata if trained was run
    meta_path = Path("artifacts/models/intent_router_v1.meta.json")
    tau_val = 0.33
    cov_val = 1.0
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            t_meta = json.load(f)
            tau_val = float(t_meta.get("validation_metrics", {}).get("tau", 0.33))
            cov_val = float(t_meta.get("validation_metrics", {}).get("coverage_at_tau", 0.9455))

    # Append test runs to audit log if split == 'test'
    if args.split == "test":
        for m, res in results.items():
            if res.get("status") != "not run" and "accuracy" in res:
                append_audit_run(
                    log_path=args.runs_log,
                    git_commit=git_commit,
                    model_name=m,
                    split_name=args.split,
                    split_sha=split_sha256,
                    accuracy=res["accuracy"],
                    macro_f1=res["macro_f1"],
                    latency_ms_mean=res["latency_ms_mean"],
                    tau=tau_val if m == "trained" else 0.0,
                    coverage=cov_val if m == "trained" else 1.0,
                )

    # Build summary report
    report = {
        "evaluation_name": "Query Intent Router Evaluation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "split": {
            "name": args.split,
            "sha256": split_sha256,
            "total_samples": len(items),
            "classes": ALL_INTENTS,
            "majority_baseline_accuracy": majority_acc,
        },
        "models": results,
        "mcnemar_test": mcnemar_res,
        "legacy_benchmark_development_set": {
            "trained": legacy_res,
            "heuristic": legacy_heur,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[SUCCESS] Full evaluation report saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
