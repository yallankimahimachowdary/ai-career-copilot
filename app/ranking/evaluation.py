"""
app/ranking/evaluation.py
-------------------------
Ranking evaluation metrics, inter-annotator agreement statistics,
significance tests, and annotation workflows for AI Career Copilot.

Includes:
- Information Retrieval: nDCG@K (nDCG@5, nDCG@10), Precision@K (Precision@5), MRR
- Inter-Annotator Agreement: Cohen's kappa (2 annotators), Fleiss' kappa (multi-annotator)
- Statistical Inference: Wilcoxon signed-rank test, Confidence Intervals (parametric & bootstrap)
- Workflows: Annotation template export/import for human relevance judgments
- Ablation: Skill-overlap removal and LLM-reranking ablation harnesses
- Provenance: Machine-readable JSON output with dataset hash, seed, and timestamps
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None


# ==============================================================================
# 1. Information Retrieval Metrics: nDCG, Precision, MRR
# ==============================================================================

def dcg_at_k(
    ranked_ids: Sequence[str],
    relevance_judgments: Dict[str, float | int],
    k: int = 10,
    method: str = "standard",
) -> float:
    """Compute Discounted Cumulative Gain at rank k.

    Args:
        ranked_ids: Ordered sequence of retrieved item IDs.
        relevance_judgments: Mapping of item ID to numeric relevance score.
        k: Maximum rank depth to evaluate.
        method: "standard" uses (2^rel - 1) / log2(i+1); "linear" uses rel / log2(i+1).

    Returns:
        DCG@k score (float >= 0.0).
    """
    if k <= 0 or not ranked_ids:
        return 0.0

    eval_items = ranked_ids[:k]
    dcg = 0.0

    for idx, item_id in enumerate(eval_items, start=1):
        rel = float(relevance_judgments.get(str(item_id), 0.0))
        if rel <= 0.0:
            continue

        discount = math.log2(idx + 1)
        if method == "standard":
            gain = (2.0 ** rel) - 1.0
        elif method == "linear":
            gain = rel
        else:
            raise ValueError(f"Unknown DCG method '{method}'. Choose 'standard' or 'linear'.")

        dcg += gain / discount

    return float(dcg)


def ndcg_at_k(
    ranked_ids: Sequence[str],
    relevance_judgments: Dict[str, float | int],
    k: int = 10,
    method: str = "standard",
) -> float:
    """Compute Normalized Discounted Cumulative Gain at rank k.

    Handles empty rankings, all-zero relevance, and missing judgments cleanly.

    Args:
        ranked_ids: Ordered sequence of retrieved item IDs.
        relevance_judgments: Mapping of item ID to numeric relevance score.
        k: Rank depth.
        method: "standard" (exponential gain) or "linear".

    Returns:
        nDCG@k score between 0.0 and 1.0.
    """
    if k <= 0 or not ranked_ids or not relevance_judgments:
        return 0.0

    actual_dcg = dcg_at_k(ranked_ids, relevance_judgments, k=k, method=method)

    # Ideal ranking: sort all relevant scores descending
    all_scores = sorted(
        [float(v) for v in relevance_judgments.values() if float(v) > 0.0],
        reverse=True,
    )
    if not all_scores:
        return 0.0

    ideal_dcg = 0.0
    for idx, rel in enumerate(all_scores[:k], start=1):
        discount = math.log2(idx + 1)
        if method == "standard":
            gain = (2.0 ** rel) - 1.0
        else:
            gain = rel
        ideal_dcg += gain / discount

    if ideal_dcg == 0.0:
        return 0.0

    ndcg = actual_dcg / ideal_dcg
    return float(min(max(ndcg, 0.0), 1.0))


def ndcg_at_5(
    ranked_ids: Sequence[str],
    relevance_judgments: Dict[str, float | int],
    method: str = "standard",
) -> float:
    """Convenience helper for nDCG@5."""
    return ndcg_at_k(ranked_ids, relevance_judgments, k=5, method=method)


def ndcg_at_10(
    ranked_ids: Sequence[str],
    relevance_judgments: Dict[str, float | int],
    method: str = "standard",
) -> float:
    """Convenience helper for nDCG@10."""
    return ndcg_at_k(ranked_ids, relevance_judgments, k=10, method=method)


def precision_at_k(
    ranked_ids: Sequence[str],
    relevance_judgments: Dict[str, float | int],
    k: int = 5,
    relevance_threshold: float = 1.0,
) -> float:
    """Compute Precision@k.

    Fraction of top-k items that meet or exceed the relevance threshold.
    """
    if k <= 0 or not ranked_ids:
        return 0.0

    eval_items = ranked_ids[:k]
    relevant_count = sum(
        1 for item_id in eval_items
        if float(relevance_judgments.get(str(item_id), 0.0)) >= relevance_threshold
    )
    return float(relevant_count / k)


def precision_at_5(
    ranked_ids: Sequence[str],
    relevance_judgments: Dict[str, float | int],
    relevance_threshold: float = 1.0,
) -> float:
    """Convenience helper for Precision@5."""
    return precision_at_k(ranked_ids, relevance_judgments, k=5, relevance_threshold=relevance_threshold)


def reciprocal_rank(
    ranked_ids: Sequence[str],
    relevance_judgments: Dict[str, float | int],
    relevance_threshold: float = 1.0,
) -> float:
    """Compute Reciprocal Rank (RR) for a single query.

    Returns 1 / rank of the first relevant item (1-indexed), or 0.0 if none found.
    """
    for idx, item_id in enumerate(ranked_ids, start=1):
        rel = float(relevance_judgments.get(str(item_id), 0.0))
        if rel >= relevance_threshold:
            return float(1.0 / idx)
    return 0.0


def mean_reciprocal_rank(
    query_rankings: Sequence[Tuple[Sequence[str], Dict[str, float | int]]],
    relevance_threshold: float = 1.0,
) -> float:
    """Compute Mean Reciprocal Rank (MRR) across multiple queries/candidates.

    Args:
        query_rankings: List of (ranked_ids, relevance_judgments) pairs.
        relevance_threshold: Score needed to consider an item relevant.
    """
    if not query_rankings:
        return 0.0

    rr_scores = [
        reciprocal_rank(ranked_ids, judgments, relevance_threshold=relevance_threshold)
        for ranked_ids, judgments in query_rankings
    ]
    return float(sum(rr_scores) / len(rr_scores))


# ==============================================================================
# 2. Inter-Annotator Agreement: Cohen's Kappa & Fleiss' Kappa
# ==============================================================================

def cohen_kappa(
    annotator1: Sequence[Any],
    annotator2: Sequence[Any],
    categories: Optional[Sequence[Any]] = None,
) -> float:
    """Compute Cohen's kappa coefficient for two annotators.

    Args:
        annotator1: Sequence of ratings from annotator 1.
        annotator2: Sequence of ratings from annotator 2.
        categories: Optional fixed list of allowed category labels.

    Returns:
        Cohen's kappa score in [-1.0, 1.0].
    """
    if len(annotator1) != len(annotator2):
        raise ValueError(
            f"Annotator rating lengths must match: len(1)={len(annotator1)}, len(2)={len(annotator2)}"
        )
    n = len(annotator1)
    if n == 0:
        return 1.0

    # Determine unique categories
    if categories is None:
        cats = sorted(list(set(annotator1).union(set(annotator2))), key=lambda x: str(x))
    else:
        cats = list(categories)

    if not cats:
        return 1.0

    cat_to_idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)

    # Build confusion matrix
    cm = np.zeros((k, k), dtype=np.float64)
    for a, b in zip(annotator1, annotator2):
        if a in cat_to_idx and b in cat_to_idx:
            cm[cat_to_idx[a], cat_to_idx[b]] += 1.0
        else:
            raise ValueError(f"Encountered rating outside category set: '{a}' or '{b}'")

    total = np.sum(cm)
    if total == 0:
        return 1.0

    # Observed agreement
    po = np.trace(cm) / total

    # Expected agreement
    row_sums = np.sum(cm, axis=1)
    col_sums = np.sum(cm, axis=0)
    pe = np.sum((row_sums * col_sums) / (total * total))

    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0

    kappa = (po - pe) / (1.0 - pe)
    return float(np.clip(kappa, -1.0, 1.0))


def fleiss_kappa(ratings_matrix: Sequence[Sequence[int]]) -> float:
    """Compute Fleiss' kappa for multiple annotators.

    Args:
        ratings_matrix: N x k array/matrix where row i gives the counts of
                        raters who assigned category j to item i.
                        Each row must sum to the same constant m (raters per item, m >= 2).

    Returns:
        Fleiss' kappa score in [-1.0, 1.0].
    """
    mat = np.array(ratings_matrix, dtype=np.float64)
    if mat.ndim != 2:
        raise ValueError(f"Ratings matrix must be 2D, got shape {mat.shape}")

    n_items, n_categories = mat.shape
    if n_items == 0 or n_categories <= 1:
        return 1.0

    # Raters per item
    m_per_item = np.sum(mat, axis=1)
    m = m_per_item[0]
    if m < 2:
        raise ValueError("Fleiss' kappa requires at least 2 raters per item (m >= 2).")

    if not np.allclose(m_per_item, m):
        raise ValueError(
            f"All items must have the same number of ratings m={m}, but row sums vary: {m_per_item.tolist()}"
        )

    total_ratings = n_items * m

    # Category proportions
    p_j = np.sum(mat, axis=0) / total_ratings

    # Subject agreement P_i
    # P_i = (sum_j n_ij^2 - m) / (m * (m - 1))
    sum_n_sq = np.sum(mat * mat, axis=1)
    p_i = (sum_n_sq - m) / (m * (m - 1))
    p_bar = np.mean(p_i)

    # Expected agreement P_e_bar = sum_j p_j^2
    p_e_bar = np.sum(p_j * p_j)

    if p_e_bar >= 1.0:
        return 1.0 if p_bar >= 1.0 else 0.0

    kappa = (p_bar - p_e_bar) / (1.0 - p_e_bar)
    return float(np.clip(kappa, -1.0, 1.0))


# ==============================================================================
# 3. Statistical Comparison & Confidence Intervals
# ==============================================================================

def wilcoxon_signed_rank_test(
    scores_a: Sequence[float],
    scores_b: Sequence[float],
    zero_method: str = "wilcox",
    alternative: str = "two-sided",
) -> Dict[str, Any]:
    """Perform a paired Wilcoxon signed-rank test comparing two ranking methods.

    Guards against small sample sizes and identical distributions without fabricating p-values.

    Args:
        scores_a: Paired metric scores for method A.
        scores_b: Paired metric scores for method B.
        zero_method: Method for handling zero differences ('wilcox', 'pratt', 'zsplit').
        alternative: 'two-sided', 'greater', or 'less'.

    Returns:
        Dictionary with statistic, p_value, sample_size, and interpretation flags.
    """
    if len(scores_a) != len(scores_b):
        raise ValueError(
            f"Paired scores length mismatch: len(A)={len(scores_a)}, len(B)={len(scores_b)}"
        )

    diffs = np.array(scores_a, dtype=np.float64) - np.array(scores_b, dtype=np.float64)
    n = len(diffs)
    non_zeros = diffs[diffs != 0.0]

    # Handle insufficient observations
    if n < 5:
        return {
            "statistic": None,
            "p_value": None,
            "sample_size": n,
            "effective_pairs": len(non_zeros),
            "insufficient_sample": True,
            "significant_0_05": False,
            "significant_0_01": False,
            "mean_difference": float(np.mean(diffs)) if n > 0 else 0.0,
            "note": "Sample size (n < 5) is too small to calculate reliable Wilcoxon p-value without valid observations.",
        }

    # All differences zero
    if len(non_zeros) == 0:
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "sample_size": n,
            "effective_pairs": 0,
            "insufficient_sample": False,
            "significant_0_05": False,
            "significant_0_01": False,
            "mean_difference": 0.0,
            "note": "All paired differences are exactly zero (identical performance).",
        }

    if scipy_stats is not None:
        try:
            res = scipy_stats.wilcoxon(
                diffs,
                zero_method=zero_method,
                alternative=alternative,
            )
            stat = float(res.statistic)
            pval = float(res.pvalue)
        except Exception as e:
            return {
                "statistic": None,
                "p_value": None,
                "sample_size": n,
                "effective_pairs": len(non_zeros),
                "insufficient_sample": False,
                "error": str(e),
                "significant_0_05": False,
                "significant_0_01": False,
                "mean_difference": float(np.mean(diffs)),
            }
    else:
        # Fallback pure python calculation
        abs_diffs = np.abs(non_zeros)
        ranks = scipy_stats.rankdata(abs_diffs) if scipy_stats else np.argsort(np.argsort(abs_diffs)) + 1.0
        w_plus = float(np.sum(ranks[non_zeros > 0]))
        w_minus = float(np.sum(ranks[non_zeros < 0]))
        stat = min(w_plus, w_minus)
        pval = 1.0  # conservative without scipy

    return {
        "statistic": stat,
        "p_value": pval,
        "sample_size": n,
        "effective_pairs": len(non_zeros),
        "insufficient_sample": False,
        "significant_0_05": bool(pval < 0.05),
        "significant_0_01": bool(pval < 0.01),
        "mean_difference": float(np.mean(diffs)),
        "note": "Computed via standard Wilcoxon signed-rank test.",
    }


def confidence_interval(
    scores: Sequence[float],
    confidence: float = 0.95,
    method: str = "t",
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> Dict[str, float]:
    """Compute confidence interval for mean metric score.

    Args:
        scores: Sequence of metric observations.
        confidence: Desired confidence level (e.g. 0.95).
        method: 't' (Student's t-distribution) or 'bootstrap'.
        n_bootstrap: Number of bootstrap resamples if method='bootstrap'.
        seed: Random seed for bootstrap reproducibility.

    Returns:
        Dict with mean, std_err, lower_bound, upper_bound, and confidence.
    """
    arr = np.array(scores, dtype=np.float64)
    n = len(arr)
    if n == 0:
        return {
            "mean": 0.0,
            "std_err": 0.0,
            "lower_bound": 0.0,
            "upper_bound": 0.0,
            "confidence": confidence,
        }

    mean_val = float(np.mean(arr))
    if n == 1 or np.allclose(arr, mean_val):
        return {
            "mean": mean_val,
            "std_err": 0.0,
            "lower_bound": mean_val,
            "upper_bound": mean_val,
            "confidence": confidence,
        }

    std_err = float(np.std(arr, ddof=1) / math.sqrt(n))

    if method == "bootstrap":
        rng = np.random.default_rng(seed)
        boot_means = [
            float(np.mean(rng.choice(arr, size=n, replace=True)))
            for _ in range(n_bootstrap)
        ]
        alpha = (1.0 - confidence) / 2.0
        lower = float(np.percentile(boot_means, alpha * 100))
        upper = float(np.percentile(boot_means, (1.0 - alpha) * 100))
    else:
        # Student's t
        if scipy_stats is not None:
            t_crit = float(scipy_stats.t.ppf((1.0 + confidence) / 2.0, df=n - 1))
        else:
            t_crit = 1.96 if confidence == 0.95 else 2.576
        margin = t_crit * std_err
        lower = mean_val - margin
        upper = mean_val + margin

    return {
        "mean": round(mean_val, 4),
        "std_err": round(std_err, 4),
        "lower_bound": round(lower, 4),
        "upper_bound": round(upper, 4),
        "confidence": confidence,
    }


# ==============================================================================
# 4. Human Relevance Judgments: Export/Import Workflow
# ==============================================================================

def export_annotation_template(
    candidate_ranking_results: Sequence[Dict[str, Any]],
    snapshot_records: Sequence[Dict[str, Any]],
    output_path: Path | str,
    k: int = 10,
    format: str = "csv",
) -> Path:
    """Export a standardized annotation template for human relevance judgments.

    Output columns: candidate_id, candidate_name, rank, job_id, job_title,
                    company_name, location, relevance (blank for annotator),
                    annotator_id, notes.

    Args:
        candidate_ranking_results: List of candidate ranking dicts (each having candidate_id, ranked_job_ids).
        snapshot_records: Master list of job dictionaries from snapshot.
        output_path: File destination (.csv or .json).
        k: Maximum items to export per candidate.
        format: 'csv' or 'json'.

    Returns:
        Path to generated template.
    """
    jobs_map = {str(j.get("id") or j.get("external_id") or ""): j for j in snapshot_records}
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []

    for cr in candidate_ranking_results:
        cand_id = str(cr.get("candidate_id") or "cand_unknown")
        cand_name = str(cr.get("candidate_name") or cand_id)
        ranked_ids = list(cr.get("ranked_job_ids", []))[:k]

        for rank_idx, jid in enumerate(ranked_ids, start=1):
            job = jobs_map.get(str(jid), {})
            rows.append({
                "candidate_id": cand_id,
                "candidate_name": cand_name,
                "rank": rank_idx,
                "job_id": str(jid),
                "job_title": job.get("title", "N/A"),
                "company_name": job.get("company_name", "N/A"),
                "location": job.get("location", "N/A"),
                "relevance": "",  # To be filled by human annotator: 0 (not relevant), 1 (partially), 2 (highly)
                "annotator_id": "",
                "notes": "",
            })

    if format.lower() == "json":
        payload = {
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "description": "Human relevance judgment annotation template",
                "instructions": "Grade relevance as 0 (Irrelevant), 1 (Partially Relevant), or 2 (Highly Relevant).",
                "scale": {"0": "Irrelevant", "1": "Partially Relevant", "2": "Highly Relevant"},
                "total_items": len(rows),
            },
            "annotations": rows,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    else:
        fieldnames = [
            "candidate_id", "candidate_name", "rank", "job_id",
            "job_title", "company_name", "location", "relevance",
            "annotator_id", "notes",
        ]
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return out_file


def import_relevance_judgments(
    input_path: Path | str,
) -> Dict[str, Dict[str, float]]:
    """Import and validate human relevance judgments from CSV or JSON.

    Returns:
        Nested dict: {candidate_id: {job_id: numeric_relevance_score}}
    """
    in_file = Path(input_path)
    if not in_file.exists():
        raise FileNotFoundError(f"Annotation file not found: {in_file}")

    judgments: Dict[str, Dict[str, float]] = {}

    if in_file.suffix.lower() == ".json":
        with open(in_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data.get("annotations", data)
            if not isinstance(items, list):
                raise ValueError("JSON annotation file must contain an 'annotations' list.")
            for row in items:
                _parse_judgment_row(row, judgments)
    else:
        with open(in_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                _parse_judgment_row(row, judgments)

    return judgments


def _parse_judgment_row(
    row: Dict[str, Any],
    judgments_accumulator: Dict[str, Dict[str, float]],
) -> None:
    cand_id = str(row.get("candidate_id") or "").strip()
    job_id = str(row.get("job_id") or "").strip()
    raw_rel = row.get("relevance")

    if not cand_id or not job_id:
        return

    # Skip unannotated rows
    if raw_rel is None or str(raw_rel).strip() == "":
        return

    try:
        rel_val = float(raw_rel)
    except ValueError:
        raise ValueError(f"Invalid non-numeric relevance '{raw_rel}' for candidate {cand_id}, job {job_id}")

    if cand_id not in judgments_accumulator:
        judgments_accumulator[cand_id] = {}
    judgments_accumulator[cand_id][job_id] = rel_val


# ==============================================================================
# 5. Ablation Studies Framework
# ==============================================================================

def run_ablation_study(
    candidate: Dict[str, Any],
    snapshot_records: List[Dict[str, Any]],
    k: int = 10,
    relevance_judgments: Optional[Dict[str, float | int]] = None,
) -> Dict[str, Any]:
    """Execute ablation experiments on ranking components.

    Compares:
    1. Full Hybrid (BM25 0.10 + SBERT 0.10 + Overlap 0.80)
    2. Ablation: No Skill Overlap (rebalanced BM25 0.50 + SBERT 0.50)
    3. Ablation: BM25 Only
    4. Ablation: SBERT Only
    5. Ablation: Overlap Only
    """
    from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
    from app.ranking.hybrid import HybridRanker

    # Instantiate rankers
    full_hybrid = HybridRanker(name="full_hybrid")
    bm25_ranker = BM25Ranker(name="ablation_bm25_only")
    sbert_ranker = SbertRanker(name="ablation_sbert_only")
    overlap_ranker = SkillOverlapRanker(name="ablation_overlap_only")

    # Ablated hybrid: zero overlap weight
    no_overlap_hybrid = HybridRanker(
        name="ablation_no_skill_overlap",
        weights={"bm25": 0.50, "sbert": 0.50, "overlap": 0.00},
    )

    rankers = {
        "full_hybrid": full_hybrid,
        "ablation_no_skill_overlap": no_overlap_hybrid,
        "ablation_bm25_only": bm25_ranker,
        "ablation_sbert_only": sbert_ranker,
        "ablation_overlap_only": overlap_ranker,
    }

    results: Dict[str, Any] = {}
    full_ranked = None

    for name, rk in rankers.items():
        res = rk.rank(candidate, snapshot_records, k=k)
        ranked_ids = res.ranked_job_ids

        entry: Dict[str, Any] = {
            "ranked_job_ids": ranked_ids,
            "scores": {jid: res.scores.get(jid, 0.0) for jid in ranked_ids},
        }

        # Compute ranking metrics if relevance judgments are available
        if relevance_judgments:
            entry["ndcg@5"] = ndcg_at_5(ranked_ids, relevance_judgments)
            entry["ndcg@10"] = ndcg_at_10(ranked_ids, relevance_judgments)
            entry["precision@5"] = precision_at_5(ranked_ids, relevance_judgments)
            entry["mrr"] = reciprocal_rank(ranked_ids, relevance_judgments)

        if name == "full_hybrid":
            full_ranked = set(ranked_ids)
            entry["jaccard_similarity_to_full"] = 1.0
        elif full_ranked is not None:
            cur_set = set(ranked_ids)
            union_len = len(full_ranked.union(cur_set))
            jaccard = len(full_ranked.intersection(cur_set)) / union_len if union_len > 0 else 0.0
            entry["jaccard_similarity_to_full"] = round(jaccard, 4)

        results[name] = entry

    return results


# ==============================================================================
# 6. Machine-Readable Provenance & Complete Evaluation Runner
# ==============================================================================

def generate_evaluation_report(
    dataset_path: Path | str,
    method_name: str,
    seed: int,
    metrics: Dict[str, Any],
    annotator_agreement: Optional[Dict[str, Any]] = None,
    statistical_comparisons: Optional[Dict[str, Any]] = None,
    ablations: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate standardized machine-readable evaluation report dictionary."""
    dpath = Path(dataset_path)
    file_hash = "n/a"
    if dpath.exists():
        with open(dpath, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

    return {
        "dataset": {
            "path": str(dpath).replace("\\", "/"),
            "sha256_hash": file_hash,
        },
        "method": method_name,
        "seed": seed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "annotator_agreement": annotator_agreement or {
            "status": "awaiting_annotations",
            "cohen_kappa": None,
            "fleiss_kappa": None,
            "note": "Inter-annotator agreement metrics await human label completion.",
        },
        "statistical_comparisons": statistical_comparisons or {},
        "ablations": ablations or {},
        "notes": notes or "Automated evaluation run.",
    }
