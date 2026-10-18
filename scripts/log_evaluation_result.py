"""Import evaluation metrics from result JSON into evaluation_logs table in PostgreSQL.

Requirements:
- Idempotent upsert on conflict (run_id, component, metric_name).
- STRICT VALIDATION: Rejects and raises ValueError if dataset_sha256 is missing or empty.
- Records metrics with sample counts, confidence intervals, params, and git commit.
- Contains NO personal data or user IDs.
"""

import argparse
import asyncio
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal

DEFAULT_EVAL_FILE = Path("results/router_eval_v1.json")


def _extract_dataset_sha256(data: Dict[str, Any]) -> str:
    """Extract and validate dataset SHA-256."""
    sha = (
        data.get("dataset_sha256")
        or (data.get("split") or {}).get("sha256")
        or (data.get("dataset") or {}).get("sha256")
    )
    if not sha or not str(sha).strip():
        raise ValueError(
            "Evaluation result rejected: dataset_sha256 is required and cannot be empty."
        )
    return str(sha).strip().upper()


async def import_evaluation_log(file_path: Path):
    print(f"Reading evaluation results from {file_path}...")
    if not file_path.exists():
        raise FileNotFoundError(f"Evaluation file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Enforce dataset_sha256 presence
    dataset_sha = _extract_dataset_sha256(data)
    print(f"Validated dataset SHA-256: {dataset_sha}")

    experiment_name = data.get("evaluation_name", "Evaluation Run")
    run_timestamp_str = data.get("timestamp")
    run_at = (
        datetime.fromisoformat(run_timestamp_str)
        if run_timestamp_str
        else datetime.now(timezone.utc)
    )
    git_commit = data.get("git_commit", "unknown")
    run_id = f"eval_{run_at.strftime('%Y%m%d_%H%M%S')}_{git_commit[:7]}"

    split_info = data.get("split", {})
    n_samples = split_info.get("total_samples")

    models_data = data.get("models", {})
    records_to_insert = []

    # If format is router_eval_v1 with models.trained / models.rules
    if models_data:
        for model_key, m_info in models_data.items():
            comp_name = f"router_{model_key}"
            ci = m_info.get("ci_95", [None, None])
            ci_low = ci[0] if len(ci) > 0 else None
            ci_high = ci[1] if len(ci) > 1 else None

            # Standard metrics
            for metric in ("accuracy", "macro_f1", "latency_ms_mean", "latency_ms_p95"):
                if metric in m_info:
                    records_to_insert.append({
                        "id": uuid.uuid4(),
                        "experiment_name": experiment_name,
                        "run_id": run_id,
                        "component": comp_name,
                        "metric_name": metric,
                        "metric_value": float(m_info[metric]),
                        "n_samples": n_samples,
                        "ci_low": ci_low if metric == "accuracy" else None,
                        "ci_high": ci_high if metric == "accuracy" else None,
                        "model_name": m_info.get("backend", model_key),
                        "model_hash": None,
                        "dataset_sha256": dataset_sha,
                        "git_commit": git_commit,
                        "seed": m_info.get("seed"),
                        "params": json.dumps({"backend": m_info.get("backend")}),
                        "notes": f"Imported from {file_path.name}",
                        "created_at": run_at,
                    })
    else:
        # Fallback flat metrics format
        metrics = data.get("metrics", {})
        for m_name, m_val in metrics.items():
            if isinstance(m_val, (int, float)):
                records_to_insert.append({
                    "id": uuid.uuid4(),
                    "experiment_name": experiment_name,
                    "run_id": run_id,
                    "component": data.get("component", "system"),
                    "metric_name": m_name,
                    "metric_value": float(m_val),
                    "n_samples": n_samples,
                    "ci_low": None,
                    "ci_high": None,
                    "model_name": data.get("model_name"),
                    "model_hash": None,
                    "dataset_sha256": dataset_sha,
                    "git_commit": git_commit,
                    "seed": None,
                    "params": json.dumps(data.get("params", {})),
                    "notes": f"Imported from {file_path.name}",
                    "created_at": run_at,
                })

    print(f"Extracted {len(records_to_insert)} evaluation metric records.")

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
        for r in records_to_insert:
            await session.execute(upsert_sql, r)
        await session.commit()

        count_res = await session.execute(text("SELECT count(*) FROM evaluation_logs"))
        total_logs = count_res.scalar()

    print("\n--- EVALUATION LOGS IMPORT SUMMARY ---")
    print(f"  Records processed : {len(records_to_insert)}")
    print(f"  Total logs in DB  : {total_logs}")
    print(f"  Dataset SHA-256   : {dataset_sha}")


def main():
    parser = argparse.ArgumentParser(description="Log evaluation results to PostgreSQL.")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_EVAL_FILE,
        help="Path to evaluation JSON result file",
    )
    args = parser.parse_args()
    asyncio.run(import_evaluation_log(args.file))


if __name__ == "__main__":
    main()
