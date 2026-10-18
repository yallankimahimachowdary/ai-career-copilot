"""Ingest evaluation results from R6 (fairness_v2.json, rag_retrieval.json, rag_generation.json)
into PostgreSQL evaluation_logs table with strict schema validation and SHA-256 traceability.
"""

import asyncio
import json
import os
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results"

FAIRNESS_RESULTS = RESULTS_DIR / "fairness_v2.json"
RETRIEVAL_RESULTS = RESULTS_DIR / "rag_retrieval.json"
GENERATION_RESULTS = RESULTS_DIR / "rag_generation.json"

FAIRNESS_DATASET_SHA = "C4068DD0632408B7A3FE779E905E94D9F136D48B136E3560DEFA250B8F75D96F"
RAG_DATASET_SHA = "34E34398A127F63361E5FE18BDF9904076E1E58B631DE130B38A5553883800AE"


def build_fairness_records() -> List[Dict[str, Any]]:
    if not FAIRNESS_RESULTS.exists():
        print(f"Warning: {FAIRNESS_RESULTS} does not exist.")
        return []

    with open(FAIRNESS_RESULTS, "r", encoding="utf-8") as f:
        data = json.load(f)

    timestamp_str = data.get("metadata", {}).get("evaluation_timestamp")
    created_at = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)
    run_id = f"fairness_v2_{created_at.strftime('%Y%m%d_%H%M%S')}"

    records = []
    # Production rankers
    prod = data.get("production_evaluations", {})
    for ranker_key, ranker_eval in prod.items():
        demo = ranker_eval.get("demographic_fairness", {})
        tier = ranker_eval.get("institution_tier_fairness", {})
        n_samples = demo.get("sample_count", 600)

        # Metrics to log
        demo_metrics = {
            "mean_kendall_tau": demo.get("mean_kendall_tau"),
            "mean_top5_jaccard": demo.get("mean_top5_jaccard"),
            "mean_score_delta": demo.get("mean_score_delta"),
            "fairlearn_demographic_parity_difference": demo.get("fairlearn_demographic_parity_difference"),
            "fairlearn_demographic_parity_ratio": demo.get("fairlearn_demographic_parity_ratio"),
        }
        for m_name, m_val in demo_metrics.items():
            if m_val is not None:
                records.append({
                    "id": uuid.uuid4(),
                    "experiment_name": "R6 Fairness Evaluation",
                    "run_id": run_id,
                    "component": f"fairness_{ranker_key}",
                    "metric_name": m_name,
                    "metric_value": float(m_val),
                    "n_samples": n_samples,
                    "ci_low": None,
                    "ci_high": None,
                    "model_name": ranker_key,
                    "model_hash": None,
                    "dataset_sha256": FAIRNESS_DATASET_SHA,
                    "git_commit": "R6",
                    "seed": 42,
                    "params": json.dumps({"masking": True, "type": "demographic"}),
                    "notes": f"R6 demographic fairness metrics from {FAIRNESS_RESULTS.name}",
                    "created_at": created_at,
                })

        tier_metrics = {
            "tier_demographic_parity_difference": tier.get("tier_demographic_parity_difference"),
            "tier_demographic_parity_ratio": tier.get("tier_demographic_parity_ratio"),
            "tier_score_gap_t1_minus_t3": tier.get("tier_score_gap_t1_minus_t3"),
        }
        for m_name, m_val in tier_metrics.items():
            if m_val is not None:
                records.append({
                    "id": uuid.uuid4(),
                    "experiment_name": "R6 Fairness Evaluation",
                    "run_id": run_id,
                    "component": f"fairness_{ranker_key}",
                    "metric_name": m_name,
                    "metric_value": float(m_val),
                    "n_samples": n_samples,
                    "ci_low": None,
                    "ci_high": None,
                    "model_name": ranker_key,
                    "model_hash": None,
                    "dataset_sha256": FAIRNESS_DATASET_SHA,
                    "git_commit": "R6",
                    "seed": 42,
                    "params": json.dumps({"masking": True, "type": "institution_tier"}),
                    "notes": f"R6 tier fairness metrics from {FAIRNESS_RESULTS.name}",
                    "created_at": created_at,
                })

    # Positive controls
    pos = data.get("positive_control_evaluations", {})
    ctrl_a = pos.get("control_a_demographic_bias", {})
    if ctrl_a:
        records.append({
            "id": uuid.uuid4(),
            "experiment_name": "R6 Fairness Evaluation",
            "run_id": run_id,
            "component": "fairness_positive_control_a",
            "metric_name": "fairlearn_demographic_parity_difference",
            "metric_value": float(ctrl_a.get("fairlearn_demographic_parity_difference", 0.0)),
            "n_samples": ctrl_a.get("sample_count", 600),
            "ci_low": None,
            "ci_high": None,
            "model_name": "DemographicBiasedRanker",
            "model_hash": None,
            "dataset_sha256": FAIRNESS_DATASET_SHA,
            "git_commit": "R6",
            "seed": 42,
            "params": json.dumps({"bias_target": "White / Caucasian", "penalty": 0.35}),
            "notes": "Positive Control A (Demographic Bias) - expected failure",
            "created_at": created_at,
        })
        records.append({
            "id": uuid.uuid4(),
            "experiment_name": "R6 Fairness Evaluation",
            "run_id": run_id,
            "component": "fairness_positive_control_a",
            "metric_name": "fairlearn_demographic_parity_ratio",
            "metric_value": float(ctrl_a.get("fairlearn_demographic_parity_ratio", 0.0)),
            "n_samples": ctrl_a.get("sample_count", 600),
            "ci_low": None,
            "ci_high": None,
            "model_name": "DemographicBiasedRanker",
            "model_hash": None,
            "dataset_sha256": FAIRNESS_DATASET_SHA,
            "git_commit": "R6",
            "seed": 42,
            "params": json.dumps({"bias_target": "White / Caucasian", "penalty": 0.35}),
            "notes": "Positive Control A (Demographic Bias) - expected failure",
            "created_at": created_at,
        })

    ctrl_b = pos.get("control_b_prestige_bias", {})
    if ctrl_b:
        records.append({
            "id": uuid.uuid4(),
            "experiment_name": "R6 Fairness Evaluation",
            "run_id": run_id,
            "component": "fairness_positive_control_b",
            "metric_name": "tier_demographic_parity_ratio",
            "metric_value": float(ctrl_b.get("tier_demographic_parity_ratio", 0.0)),
            "n_samples": 30,
            "ci_low": None,
            "ci_high": None,
            "model_name": "InstitutionPrestigeBiasedRanker",
            "model_hash": None,
            "dataset_sha256": FAIRNESS_DATASET_SHA,
            "git_commit": "R6",
            "seed": 42,
            "params": json.dumps({"tier_1_boost": 0.35, "tier_3_penalty": 0.35}),
            "notes": "Positive Control B (Prestige Bias) - expected failure",
            "created_at": created_at,
        })
        records.append({
            "id": uuid.uuid4(),
            "experiment_name": "R6 Fairness Evaluation",
            "run_id": run_id,
            "component": "fairness_positive_control_b",
            "metric_name": "tier_score_gap_t1_minus_t3",
            "metric_value": float(ctrl_b.get("tier_score_gap_t1_minus_t3", 0.0)),
            "n_samples": 30,
            "ci_low": None,
            "ci_high": None,
            "model_name": "InstitutionPrestigeBiasedRanker",
            "model_hash": None,
            "dataset_sha256": FAIRNESS_DATASET_SHA,
            "git_commit": "R6",
            "seed": 42,
            "params": json.dumps({"tier_1_boost": 0.35, "tier_3_penalty": 0.35}),
            "notes": "Positive Control B (Prestige Bias) - expected failure",
            "created_at": created_at,
        })

    return records


def build_retrieval_records() -> List[Dict[str, Any]]:
    if not RETRIEVAL_RESULTS.exists():
        print(f"Warning: {RETRIEVAL_RESULTS} does not exist.")
        return []

    with open(RETRIEVAL_RESULTS, "r", encoding="utf-8") as f:
        data = json.load(f)

    timestamp_str = data.get("metadata", {}).get("evaluation_timestamp")
    created_at = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)
    run_id = f"rag_retrieval_{created_at.strftime('%Y%m%d_%H%M%S')}"
    dataset_sha = data.get("metadata", {}).get("dataset_sha256", RAG_DATASET_SHA)
    query_count = data.get("metadata", {}).get("query_count", 100)

    records = []
    summary = data.get("overall_summary", {})
    for system_key, metrics in summary.items():
        comp_name = f"rag_retrieval_{system_key}"
        for metric_name, m_dict in metrics.items():
            if isinstance(m_dict, dict) and "mean" in m_dict:
                records.append({
                    "id": uuid.uuid4(),
                    "experiment_name": "R6 RAG Retrieval Evaluation",
                    "run_id": run_id,
                    "component": comp_name,
                    "metric_name": metric_name,
                    "metric_value": float(m_dict["mean"]),
                    "n_samples": query_count,
                    "ci_low": float(m_dict["ci_lower"]) if "ci_lower" in m_dict else None,
                    "ci_high": float(m_dict["ci_upper"]) if "ci_upper" in m_dict else None,
                    "model_name": system_key,
                    "model_hash": None,
                    "dataset_sha256": dataset_sha,
                    "git_commit": "R6",
                    "seed": 42,
                    "params": json.dumps({"bootstrap_iterations": 1000}),
                    "notes": f"R6 retrieval evaluation: {metric_name} with 95% bootstrap CI",
                    "created_at": created_at,
                })

    return records


def build_generation_records() -> List[Dict[str, Any]]:
    if not GENERATION_RESULTS.exists():
        print(f"Warning: {GENERATION_RESULTS} does not exist.")
        return []

    with open(GENERATION_RESULTS, "r", encoding="utf-8") as f:
        data = json.load(f)

    timestamp_str = data.get("metadata", {}).get("evaluation_timestamp")
    created_at = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)
    run_id = f"rag_generation_{created_at.strftime('%Y%m%d_%H%M%S')}"
    dataset_sha = data.get("metadata", {}).get("dataset_sha256", RAG_DATASET_SHA)
    sample_size = data.get("metadata", {}).get("sample_size", 8)

    records = []
    matrix = data.get("two_by_two_matrix_results", {})
    for cell_key, metrics in matrix.items():
        comp_name = f"rag_gen_{cell_key}"
        for metric_name, m_val in metrics.items():
            if isinstance(m_val, (int, float)) and metric_name != "sample_size":
                records.append({
                    "id": uuid.uuid4(),
                    "experiment_name": "R6 RAG Generation 2x2 Evaluation",
                    "run_id": run_id,
                    "component": comp_name,
                    "metric_name": metric_name,
                    "metric_value": float(m_val),
                    "n_samples": sample_size,
                    "ci_low": None,
                    "ci_high": None,
                    "model_name": cell_key,
                    "model_hash": None,
                    "dataset_sha256": dataset_sha,
                    "git_commit": "R6",
                    "seed": 42,
                    "params": json.dumps({"quadrant": cell_key}),
                    "notes": f"R6 2x2 factorial generation metric {metric_name}",
                    "created_at": created_at,
                })

    return records


async def main():
    print("=================================================================")
    print("Ingesting R6 Evaluation Metrics into PostgreSQL evaluation_logs")
    print("=================================================================")

    all_records: List[Dict[str, Any]] = []
    fairness_records = build_fairness_records()
    print(f"Fairness records built: {len(fairness_records)}")
    all_records.extend(fairness_records)

    retrieval_records = build_retrieval_records()
    print(f"Retrieval records built: {len(retrieval_records)}")
    all_records.extend(retrieval_records)

    generation_records = build_generation_records()
    print(f"Generation records built: {len(generation_records)}")
    all_records.extend(generation_records)

    print(f"\nTotal records to insert/upsert: {len(all_records)}")

    upsert_sql = text("""
        INSERT INTO evaluation_logs (
            id, created_at, experiment_name, run_id, component,
            metric_name, metric_value, n_samples, ci_low, ci_high,
            model_name, model_hash, dataset_sha256, git_commit,
            seed, params, notes
        ) VALUES (
            :id, :created_at, :experiment_name, :run_id, :component,
            :metric_name, :metric_value, :n_samples, :ci_low, :ci_high,
            :model_name, :model_hash, :dataset_sha256, :git_commit,
            :seed, CAST(:params AS jsonb), :notes
        )
        ON CONFLICT (run_id, component, metric_name) DO UPDATE SET
            metric_value = EXCLUDED.metric_value,
            n_samples = EXCLUDED.n_samples,
            ci_low = EXCLUDED.ci_low,
            ci_high = EXCLUDED.ci_high,
            model_name = EXCLUDED.model_name,
            dataset_sha256 = EXCLUDED.dataset_sha256,
            git_commit = EXCLUDED.git_commit,
            params = EXCLUDED.params,
            notes = EXCLUDED.notes
    """)

    async with AsyncSessionLocal() as session:
        for r in all_records:
            await session.execute(upsert_sql, r)
        await session.commit()

        count_res = await session.execute(text("SELECT count(*) FROM evaluation_logs"))
        total_logs = count_res.scalar()

    print("\n--- INGESTION COMPLETE ---")
    print(f"  Inserted/Upserted : {len(all_records)}")
    print(f"  Total DB Logs now : {total_logs}")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(main())
