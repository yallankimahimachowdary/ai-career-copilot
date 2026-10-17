"""Compute raw inter-annotator agreement and Cohen's kappa on filled audit CSV.

Usage:
  python scripts/score_router_label_audit.py --csv results/router_label_audit_sample.csv
  python scripts/score_router_label_audit.py --test-mock
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import List, Tuple

from sklearn.metrics import cohen_kappa_score


def score_audit_csv(csv_path: Path) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(f"Audit CSV file not found: {csv_path}")

    annotator_1: List[str] = []
    annotator_2: List[str] = []
    consensus: List[str] = []
    ids: List[str] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            a1 = row.get("annotator_1_intent", "").strip().lower()
            a2 = row.get("annotator_2_intent", "").strip().lower()
            con = row.get("consensus_intent", "").strip().lower()
            ids.append(row.get("id", ""))
            annotator_1.append(a1)
            annotator_2.append(a2)
            consensus.append(con)

    total_rows = len(ids)
    if total_rows == 0:
        raise ValueError("Audit CSV is empty.")

    # Check for empty annotations
    filled_mask = [bool(a1 and a2) for a1, a2 in zip(annotator_1, annotator_2)]
    filled_count = sum(filled_mask)

    if filled_count == 0:
        return {
            "status": "UNFILLED",
            "message": f"Audit CSV contains {total_rows} items, but no annotations are filled yet.",
            "total_items": total_rows,
            "filled_items": 0,
        }

    # Filter to filled rows
    y1 = [a1 for a1, m in zip(annotator_1, filled_mask) if m]
    y2 = [a2 for a2, m in zip(annotator_2, filled_mask) if m]

    # Compute raw agreement
    agreements = sum(1 for a, b in zip(y1, y2) if a == b)
    raw_agreement = agreements / len(y1)

    # Compute Cohen's kappa
    kappa = cohen_kappa_score(y1, y2)

    return {
        "status": "SCORED",
        "total_items": total_rows,
        "filled_items": len(y1),
        "agreements": agreements,
        "raw_agreement": float(raw_agreement),
        "cohens_kappa": float(kappa),
    }


def run_mock_test():
    """Runs a verification test with synthetic mock annotator labels."""
    print("[MOCK TEST] Generating mock annotations to verify scoring calculation...")
    mock_data = [
        ("id_01", "job_search", "job_search"),
        ("id_02", "job_search", "job_search"),
        ("id_03", "skill_gap_analysis", "skill_gap_analysis"),
        ("id_04", "resume_feedback", "resume_feedback"),
        ("id_05", "career_advice", "career_advice"),
        ("id_06", "interview_preparation", "interview_preparation"),
        ("id_07", "job_search", "skill_gap_analysis"),  # disagreement
        ("id_08", "resume_feedback", "career_advice"),   # disagreement
        ("id_09", "interview_preparation", "interview_preparation"),
        ("id_10", "career_advice", "career_advice"),
    ]
    y1 = [x[1] for x in mock_data]
    y2 = [x[2] for x in mock_data]
    agreements = sum(1 for a, b in zip(y1, y2) if a == b)
    raw_acc = agreements / len(y1)
    kappa = cohen_kappa_score(y1, y2)
    print(f"Mock Items: {len(mock_data)}")
    print(f"Agreements: {agreements}/{len(mock_data)} ({raw_acc * 100:.1f}%)")
    print(f"Cohen's Kappa: {kappa:.4f}")
    assert raw_acc == 0.8, f"Expected 0.8 raw agreement, got {raw_acc}"
    assert kappa > 0.7, f"Expected kappa > 0.7, got {kappa}"
    print("[MOCK TEST SUCCESS] scoring logic verified successfully.")


def main():
    parser = argparse.ArgumentParser(description="Score router label audit CSV")
    parser.add_argument("--csv", type=Path, default=Path("results/router_label_audit_sample.csv"))
    parser.add_argument("--test-mock", action="store_true", help="Run self-test on mock data")
    args = parser.parse_args()

    if args.test_mock:
        run_mock_test()
        return

    result = score_audit_csv(args.csv)
    print("=====================================================")
    print("ROUTER LABEL AUDIT SCORING REPORT")
    print("=====================================================")
    for k, v in result.items():
        if isinstance(v, float):
            print(f"  {k:<20}: {v:.4f}")
        else:
            print(f"  {k:<20}: {v}")
    print("=====================================================")


if __name__ == "__main__":
    main()
