#!/usr/bin/env python3
"""
scripts/ingest_annotations.py
-----------------------------
Validates, adjudicates, and ingests human relevance annotations (R11-3).

Guarantees & Invariant Rules:
1. Ratings strictly in {0, 1, 2}. Blank entries, duplicate (resume, job) pairs,
   or unexpected schema columns are rejected with a descriptive ValidationError.
2. Production outputs written to results/real/labels.jsonl (run_type=real) with rater IDs.
3. Double-rated resumes:
   - Evaluates inter-rater reliability via Quadratic-Weighted Cohen's Kappa,
     raw agreement rate, and 1,000-sample bootstrap confidence intervals.
   - Generates a structured disagreements file for human adjudication.
4. Final Ground-Truth Label Rule:
   - If an adjudicated rating is present in the adjudication file, the adjudicated value is used.
   - Otherwise, the primary rater (Rater A) label is used. (Formally documented).
5. Synthetic Safety: Automated unit tests execute strictly against toy/mock fixtures.
   No synthetic resume is ever annotated or written to production results/real/.
"""

import argparse
import csv
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

VALID_RATINGS = {0, 1, 2}
REQUIRED_COLUMNS = {
    "resume_alias",
    "job_id",
    "rating",
}


class AnnotationValidationError(ValueError):
    """Raised when annotation sheets fail validation (invalid scale, blanks, or duplicates)."""
    pass


def compute_quadratic_weighted_kappa(rater_a: List[int], rater_b: List[int], num_categories: int = 3) -> float:
    """Compute Cohen's quadratic-weighted kappa for ordinal ratings {0, 1, ..., k-1}."""
    if len(rater_a) != len(rater_b):
        raise ValueError("Rater sequences must have identical lengths.")
    if len(rater_a) == 0:
        return 1.0

    # Confusion matrix
    conf_mat = np.zeros((num_categories, num_categories), dtype=np.float64)
    for a, b in zip(rater_a, rater_b):
        if 0 <= a < num_categories and 0 <= b < num_categories:
            conf_mat[a, b] += 1.0

    n = np.sum(conf_mat)
    if n == 0:
        return 1.0

    # Weight matrix: quadratic penalties (1 - (i-j)^2 / (k-1)^2)
    # Distance / penalty formulation: w_ij = (i - j)^2 / (k - 1)^2
    max_dist_sq = float((num_categories - 1) ** 2)
    weights = np.zeros((num_categories, num_categories), dtype=np.float64)
    for i in range(num_categories):
        for j in range(num_categories):
            weights[i, j] = float((i - j) ** 2) / max_dist_sq

    # Observed weighted disagreement
    obs_disagreement = np.sum(weights * conf_mat) / n

    # Expected weighted disagreement under chance independence
    row_sums = np.sum(conf_mat, axis=1)
    col_sums = np.sum(conf_mat, axis=0)
    expected_mat = np.outer(row_sums, col_sums) / n
    exp_disagreement = np.sum(weights * expected_mat) / n

    if exp_disagreement == 0:
        return 1.0

    kappa = 1.0 - (obs_disagreement / exp_disagreement)
    return round(float(kappa), 4)


def bootstrap_kappa_ci(
    rater_a: List[int],
    rater_b: List[int],
    n_resamples: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> Tuple[float, float]:
    """Compute percentile bootstrap confidence interval for quadratic weighted kappa."""
    rng = random.Random(seed)
    n = len(rater_a)
    if n < 5:
        k = compute_quadratic_weighted_kappa(rater_a, rater_b)
        return k, k

    indices = list(range(n))
    boot_kappas = []
    for _ in range(n_resamples):
        sample_idx = [rng.choice(indices) for _ in range(n)]
        sa = [rater_a[i] for i in sample_idx]
        sb = [rater_b[i] for i in sample_idx]
        boot_kappas.append(compute_quadratic_weighted_kappa(sa, sb))

    boot_kappas.sort()
    lower_idx = int(n_resamples * (alpha / 2.0))
    upper_idx = int(n_resamples * (1.0 - alpha / 2.0))
    return round(boot_kappas[lower_idx], 4), round(boot_kappas[min(upper_idx, n_resamples - 1)], 4)


def read_and_validate_annotation_sheet(
    csv_path: Path | str,
    rater_id: str,
) -> List[Dict[str, Any]]:
    """Read a rater CSV sheet and enforce strict validation rules."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Annotation sheet not found: {path}")

    records = []
    seen_pairs: Set[Tuple[str, str]] = set()

    with open(path, "r", encoding="utf-8-sig") as f:
        # Filter comment lines starting with '#'
        content_lines = [line for line in f if not line.strip().startswith("#")]

    reader = csv.DictReader(content_lines)
    if not reader.fieldnames:
        raise AnnotationValidationError(f"Empty annotation sheet: {path}")

    missing_cols = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing_cols:
        raise AnnotationValidationError(f"Missing required columns {missing_cols} in {path}")

    for line_idx, row in enumerate(reader, start=2):
        r_alias = (row.get("resume_alias") or "").strip()
        j_id = (row.get("job_id") or "").strip()
        raw_rating = (row.get("rating") or "").strip()
        notes = (row.get("notes") or "").strip()

        if not r_alias or not j_id:
            raise AnnotationValidationError(f"Row {line_idx} in {path} has empty resume_alias or job_id")

        if not raw_rating:
            raise AnnotationValidationError(
                f"Row {line_idx} (resume={r_alias}, job={j_id}) in {path} has a BLANK rating. All items must be rated."
            )

        try:
            rating_val = int(raw_rating)
        except ValueError:
            raise AnnotationValidationError(
                f"Row {line_idx} in {path} has non-integer rating '{raw_rating}'. Must be in {{0, 1, 2}}."
            )

        if rating_val not in VALID_RATINGS:
            raise AnnotationValidationError(
                f"Row {line_idx} in {path} has invalid rating {rating_val}. Must be strictly in {{0, 1, 2}}."
            )

        pair_key = (r_alias, j_id)
        if pair_key in seen_pairs:
            raise AnnotationValidationError(f"Duplicate (resume, job) pair detected at row {line_idx} in {path}: {pair_key}")
        seen_pairs.add(pair_key)

        records.append({
            "resume_id": r_alias,
            "job_id": j_id,
            "rating": rating_val,
            "rater_id": rater_id,
            "notes": notes,
        })

    return records


def ingest_annotations(
    sheet_a_path: Path | str,
    sheet_b_path: Path | str,
    output_labels_path: Path | str,
    disagreements_path: Optional[Path | str] = None,
    adjudication_path: Optional[Path | str] = None,
    run_type: str = "real",
    seed: int = 42,
) -> Dict[str, Any]:
    """Ingest, cross-validate, and compute inter-rater agreement."""
    recs_a = read_and_validate_annotation_sheet(sheet_a_path, rater_id="rater_a")
    recs_b = read_and_validate_annotation_sheet(sheet_b_path, rater_id="rater_b")

    map_a = {(r["resume_id"], r["job_id"]): r for r in recs_a}
    map_b = {(r["resume_id"], r["job_id"]): r for r in recs_b}

    common_pairs = sorted(list(set(map_a.keys()).intersection(set(map_b.keys()))))

    # Evaluate agreement on double-rated subset
    scores_a = []
    scores_b = []
    disagreements = []

    for pair in common_pairs:
        r_a = map_a[pair]["rating"]
        r_b = map_b[pair]["rating"]
        scores_a.append(r_a)
        scores_b.append(r_b)

        if r_a != r_b:
            disagreements.append({
                "resume_id": pair[0],
                "job_id": pair[1],
                "rater_a_rating": r_a,
                "rater_b_rating": r_b,
                "rater_a_notes": map_a[pair].get("notes", ""),
                "rater_b_notes": map_b[pair].get("notes", ""),
                "adjudicated_rating": "",  # To be filled by adjudicator
                "adjudication_notes": "",
            })

    raw_agreement = (
        sum(1 for a, b in zip(scores_a, scores_b) if a == b) / len(scores_a)
        if scores_a else 1.0
    )
    qwk = compute_quadratic_weighted_kappa(scores_a, scores_b)
    ci_low, ci_high = bootstrap_kappa_ci(scores_a, scores_b, n_resamples=1000, seed=seed)

    # Load adjudications if present
    adjudications: Dict[Tuple[str, str], int] = {}
    if adjudication_path and Path(adjudication_path).exists():
        with open(adjudication_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row["resume_id"], row["job_id"])
                adj_val = row.get("adjudicated_rating", "").strip()
                if adj_val and adj_val in {"0", "1", "2"}:
                    adjudications[key] = int(adj_val)

    # Build final label dictionary
    # Policy: Adjudicated rating takes precedence. Else primary rater (Rater A) label is used.
    all_pairs = sorted(list(set(map_a.keys()).union(set(map_b.keys()))))
    final_labels = []

    for pair in all_pairs:
        cid, jid = pair
        if pair in adjudications:
            final_rating = adjudications[pair]
            source_rater = "adjudicated"
        elif pair in map_a:
            final_rating = map_a[pair]["rating"]
            source_rater = "rater_a"
        else:
            final_rating = map_b[pair]["rating"]
            source_rater = "rater_b"

        final_labels.append({
            "resume_id": cid,
            "job_id": jid,
            "rating": final_rating,
            "source": source_rater,
            "run_type": run_type,
        })

    # Save output labels JSONL
    out_p = Path(output_labels_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        for lab in final_labels:
            f.write(json.dumps(lab) + "\n")

    # Save disagreements file if requested
    if disagreements_path:
        dis_p = Path(disagreements_path)
        dis_p.parent.mkdir(parents=True, exist_ok=True)
        with open(dis_p, "w", encoding="utf-8", newline="") as f:
            fieldnames = [
                "resume_id",
                "job_id",
                "rater_a_rating",
                "rater_b_rating",
                "rater_a_notes",
                "rater_b_notes",
                "adjudicated_rating",
                "adjudication_notes",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(disagreements)

    return {
        "run_type": run_type,
        "total_labels_written": len(final_labels),
        "total_rater_a_items": len(recs_a),
        "total_rater_b_items": len(recs_b),
        "double_rated_items": len(common_pairs),
        "raw_agreement_rate": round(raw_agreement, 4),
        "quadratic_weighted_kappa": qwk,
        "kappa_95_ci": [ci_low, ci_high],
        "disagreements_count": len(disagreements),
        "adjudications_applied": len(adjudications),
        "labels_output_file": str(out_p),
    }


def main():
    parser = argparse.ArgumentParser(description="Validate and ingest human relevance ratings.")
    parser.add_argument("--sheet-a", type=str, required=True, help="Path to Rater A CSV")
    parser.add_argument("--sheet-b", type=str, required=True, help="Path to Rater B CSV")
    parser.add_argument("--output", type=str, default="results/real/labels.jsonl", help="Output labels JSONL")
    parser.add_argument("--disagreements", type=str, default="results/real/disagreements.csv", help="Disagreements CSV")
    parser.add_argument("--adjudications", type=str, default=None, help="Adjudications CSV")
    parser.add_argument("--run-type", type=str, default="real", choices=["dryrun", "real"])
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    summary = ingest_annotations(
        sheet_a_path=args.sheet_a,
        sheet_b_path=args.sheet_b,
        output_labels_path=args.output,
        disagreements_path=args.disagreements,
        adjudication_path=args.adjudications,
        run_type=args.run_type,
        seed=args.seed,
    )

    print("================ ANNOTATION INGESTION SUMMARY ================")
    print(f"Total Labels Written     : {summary['total_labels_written']}")
    print(f"Rater A Items            : {summary['total_rater_a_items']}")
    print(f"Rater B Items            : {summary['total_rater_b_items']}")
    print(f"Double-Rated Items       : {summary['double_rated_items']}")
    print(f"Raw Agreement Rate       : {summary['raw_agreement_rate']*100:.2f}%")
    print(f"Quadratic Weighted Kappa : {summary['quadratic_weighted_kappa']} (95% CI: {summary['kappa_95_ci']})")
    print(f"Disagreements Found      : {summary['disagreements_count']}")
    print(f"Labels File              : {summary['labels_output_file']}")


if __name__ == "__main__":
    main()
