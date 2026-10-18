"""scripts/score_rag_human_validation.py
---------------------------------------
Computes inter-annotator agreement (Cohen's Kappa) for the blinded RAG human validation sample.

Accepts:
- CSV file with columns 'annotator_1_score' and 'annotator_2_score' (Likert 1-5 scale).

Outputs:
- Percent agreement
- Cohen's Kappa (unweighted)
- Weighted Kappa (quadratic)
- Summary by system alias
"""

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import numpy as np


def compute_cohens_kappa(rater1: List[int], rater2: List[int], min_val: int = 1, max_val: int = 5) -> Tuple[float, float, float]:
    """Computes observed agreement, expected agreement, and Cohen's Kappa."""
    if len(rater1) != len(rater2) or not rater1:
        return 0.0, 0.0, 0.0

    n = len(rater1)
    categories = list(range(min_val, max_val + 1))
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    num_cats = len(categories)

    matrix = np.zeros((num_cats, num_cats), dtype=int)
    for r1, r2 in zip(rater1, rater2):
        if r1 in cat_to_idx and r2 in cat_to_idx:
            matrix[cat_to_idx[r1], cat_to_idx[r2]] += 1

    # Observed agreement
    observed = np.trace(matrix) / n

    # Expected agreement
    row_sums = np.sum(matrix, axis=1)
    col_sums = np.sum(matrix, axis=0)
    expected = np.sum((row_sums * col_sums) / (n * n))

    if expected == 1.0:
        kappa = 1.0
    else:
        kappa = (observed - expected) / (1.0 - expected)

    return float(observed), float(expected), float(kappa)


def compute_weighted_kappa(rater1: List[int], rater2: List[int], min_val: int = 1, max_val: int = 5) -> float:
    """Computes quadratic weighted Cohen's Kappa."""
    n = len(rater1)
    if n == 0:
        return 0.0

    categories = list(range(min_val, max_val + 1))
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}
    k = len(categories)

    matrix = np.zeros((k, k), dtype=float)
    for r1, r2 in zip(rater1, rater2):
        if r1 in cat_to_idx and r2 in cat_to_idx:
            matrix[cat_to_idx[r1], cat_to_idx[r2]] += 1.0

    # Weight matrix (quadratic penalty)
    weights = np.zeros((k, k), dtype=float)
    for i in range(k):
        for j in range(k):
            weights[i, j] = ((i - j) ** 2) / ((k - 1) ** 2)

    hist1 = np.sum(matrix, axis=1)
    hist2 = np.sum(matrix, axis=0)

    expected = np.outer(hist1, hist2) / n

    po = np.sum(weights * matrix) / n
    pe = np.sum(weights * expected) / n

    if pe == 0:
        return 1.0
    return float(1.0 - (po / pe))


def main():
    parser = argparse.ArgumentParser(description="Score RAG Human Validation Sample.")
    parser.add_argument(
        "--csv",
        type=str,
        default="results/rag_human_validation_sample.csv",
        help="Path to human validation sample CSV",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist!")
        sys.exit(1)

    r1_scores: List[int] = []
    r2_scores: List[int] = []
    by_system: Dict[str, List[int]] = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s1 = row.get("annotator_1_score", "").strip()
            s2 = row.get("annotator_2_score", "").strip()
            alias = row.get("system_alias", "unknown")

            if s1 and s2:
                try:
                    val1 = int(round(float(s1)))
                    val2 = int(round(float(s2)))
                    r1_scores.append(val1)
                    r2_scores.append(val2)
                    if alias not in by_system:
                        by_system[alias] = []
                    by_system[alias].extend([val1, val2])
                except ValueError:
                    pass

    print("=================================================================")
    print("RAG Human Validation Scoring & Inter-Rater Reliability")
    print("=================================================================")
    print(f"File evaluated: {csv_path}")
    print(f"Annotated pairs found: {len(r1_scores)}")

    if not r1_scores:
        print("\nNote: Annotator scores are currently blank (awaiting human grading).")
        print("To annotate, open the CSV and fill columns 'annotator_1_score' and 'annotator_2_score' with Likert ratings (1 to 5).")
        print("=================================================================")
        return

    observed, expected, kappa = compute_cohens_kappa(r1_scores, r2_scores)
    weighted_k = compute_weighted_kappa(r1_scores, r2_scores)

    print(f"\nObserved Agreement: {observed * 100:.2f}%")
    print(f"Expected Agreement: {expected * 100:.2f}%")
    print(f"Cohen's Kappa (unweighted): {kappa:.4f}")
    print(f"Quadratic Weighted Kappa:  {weighted_k:.4f}")

    # Interpretation
    if kappa >= 0.81:
        interp = "Almost Perfect Agreement"
    elif kappa >= 0.61:
        interp = "Substantial Agreement"
    elif kappa >= 0.41:
        interp = "Moderate Agreement"
    elif kappa >= 0.21:
        interp = "Fair Agreement"
    else:
        interp = "Slight / Poor Agreement"
    print(f"Agreement Level: {interp}")

    if by_system:
        print("\nMean Human Scores by Blinded System:")
        for sys_name, scores in sorted(by_system.items()):
            print(f"  {sys_name}: Mean {np.mean(scores):.2f} (N={len(scores)//2} ratings)")

    print("=================================================================")


if __name__ == "__main__":
    main()
