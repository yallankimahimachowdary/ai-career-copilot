"""
app/ranking/fairness.py
-----------------------
Name-Swap Invariance and Fairness Evaluation Module (Phase 7).

Evaluates whether changing candidate names on otherwise identical resumes causes
algorithmic ranking score displacement or recommendation drift.

Key Principles:
1. Exact input parity: All qualifications, experiences, skills, education, and text are identical.
2. Synthetic / balanced test names across cultural backgrounds.
3. No demographic inference: Names are treated as surface token perturbations without inferring real demographic traits.
4. Distinguishes algorithmic name invariance testing from demographic fairness audits.
"""

import copy
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import numpy as np

from app.ranking.base import BaseRanker
from app.ranking.evaluation import confidence_interval


# Representative synthetic evaluation names across cultural/regional naming conventions
DEFAULT_SYNTHETIC_NAMES = [
    # South Asian
    "Ananya Rao",
    "Aarav Sharma",
    "Rohan Patel",
    "Priya Nair",
    # Western / Anglo
    "Alex Morgan",
    "Emily Johnson",
    "Christopher Smith",
    "Jordan Taylor",
    # East / Southeast Asian
    "Wei Chen",
    "Minh Nguyen",
    "Hana Kim",
    # African / African-American diaspora
    "Amara Okafor",
    "Malik Washington",
    "Keisha Jackson",
    # Hispanic / Latinx
    "Mateo Rodriguez",
    "Sofia Hernandez",
    "Carlos Ramirez",
    # Middle Eastern
    "Fatima Al-Mansoor",
    "Tariq Haddad",
    "Zainab Khan",
]


class NameSwapFairnessEvaluator:
    """Evaluates algorithmic ranking invariance under candidate name substitutions."""

    def __init__(
        self,
        ranker: BaseRanker,
        synthetic_names: Optional[List[str]] = None,
        seed: int = 42,
    ):
        self.ranker = ranker
        self.synthetic_names = synthetic_names or DEFAULT_SYNTHETIC_NAMES
        self.seed = seed

    def evaluate_profile(
        self,
        base_resume: Dict[str, Any],
        job_pool: List[Dict[str, Any]],
        name_variants: Optional[List[str]] = None,
        k_values: Tuple[int, ...] = (5, 10),
    ) -> Dict[str, Any]:
        """
        Evaluate a single resume profile across multiple name variations:
        - Keeps skills, experience, summary, and education identical.
        - Computes score and rank variance across all jobs in the pool.
        - Measures Jaccard similarity of top-K recommendations between pairs.
        """
        variants = name_variants or self.synthetic_names
        profile_results: Dict[str, Any] = {}

        # 1. Run ranking for each name variant
        run_outputs: Dict[str, Dict[str, Any]] = {}

        for name in variants:
            res_variant = copy.deepcopy(base_resume)
            res_variant["candidate_name"] = name
            # Update contact_info if present
            if "contact_info" in res_variant and isinstance(res_variant["contact_info"], dict):
                res_variant["contact_info"]["name"] = name
            # Clear pre-computed embedding to force re-computation/fair evaluation
            res_variant.pop("embedding", None)

            rank_res = self.ranker.rank(res_variant, job_pool, k=len(job_pool))
            run_outputs[name] = {
                "scores": rank_res.scores,
                "ranked_ids": rank_res.ranked_job_ids,
            }

        # 2. Pairwise comparison across name variants
        variant_names = list(run_outputs.keys())
        n_variants = len(variant_names)

        pairwise_max_score_diffs: List[float] = []
        pairwise_mean_score_diffs: List[float] = []
        pairwise_rank_displacements: List[float] = []
        pairwise_top5_jaccards: List[float] = []
        pairwise_top10_jaccards: List[float] = []

        job_ids = [str(j.get("id") or j.get("external_id") or "") for j in job_pool]

        for i in range(n_variants):
            for j in range(i + 1, n_variants):
                name_a = variant_names[i]
                name_b = variant_names[j]

                scores_a = run_outputs[name_a]["scores"]
                scores_b = run_outputs[name_b]["scores"]
                ranks_a = run_outputs[name_a]["ranked_ids"]
                ranks_b = run_outputs[name_b]["ranked_ids"]

                # Score differences across jobs
                score_diffs = [abs(scores_a.get(jid, 0.0) - scores_b.get(jid, 0.0)) for jid in job_ids]
                max_diff = float(max(score_diffs)) if score_diffs else 0.0
                mean_diff = float(np.mean(score_diffs)) if score_diffs else 0.0

                pairwise_max_score_diffs.append(max_diff)
                pairwise_mean_score_diffs.append(mean_diff)

                # Rank displacement (average absolute position change across jobs)
                rank_map_a = {jid: idx + 1 for idx, jid in enumerate(ranks_a)}
                rank_map_b = {jid: idx + 1 for idx, jid in enumerate(ranks_b)}
                rank_diffs = [abs(rank_map_a.get(jid, len(job_pool)) - rank_map_b.get(jid, len(job_pool))) for jid in job_ids]
                mean_rank_disp = float(np.mean(rank_diffs)) if rank_diffs else 0.0
                pairwise_rank_displacements.append(mean_rank_disp)

                # Top-K Jaccard overlap
                top5_a = set(ranks_a[:5])
                top5_b = set(ranks_b[:5])
                top5_jaccard = len(top5_a & top5_b) / len(top5_a | top5_b) if (top5_a | top5_b) else 1.0
                pairwise_top5_jaccards.append(top5_jaccard)

                top10_a = set(ranks_a[:10])
                top10_b = set(ranks_b[:10])
                top10_jaccard = len(top10_a & top10_b) / len(top10_a | top10_b) if (top10_a | top10_b) else 1.0
                pairwise_top10_jaccards.append(top10_jaccard)

        total_pairs = len(pairwise_max_score_diffs)
        invariance_count = sum(1 for d in pairwise_max_score_diffs if d < 1e-4)
        invariance_rate = invariance_count / total_pairs if total_pairs > 0 else 1.0

        return {
            "candidate_id": f"cand_anon_{hashlib.sha256(str(base_resume.get('id') or base_resume.get('candidate_name', 'anon')).encode()).hexdigest()[:10]}",
            "name_variants_evaluated": n_variants,
            "pairwise_comparisons": total_pairs,
            "score_invariance_rate": round(invariance_rate, 4),
            "max_abs_score_difference": round(float(max(pairwise_max_score_diffs)), 6) if pairwise_max_score_diffs else 0.0,
            "mean_abs_score_difference": round(float(np.mean(pairwise_mean_score_diffs)), 6) if pairwise_mean_score_diffs else 0.0,
            "mean_rank_displacement": round(float(np.mean(pairwise_rank_displacements)), 4) if pairwise_rank_displacements else 0.0,
            "mean_top5_jaccard_similarity": round(float(np.mean(pairwise_top5_jaccards)), 4) if pairwise_top5_jaccards else 1.0,
            "mean_top10_jaccard_similarity": round(float(np.mean(pairwise_top10_jaccards)), 4) if pairwise_top10_jaccards else 1.0,
            "tested_names_sample": variants[:5],
        }

    def evaluate_profiles_batch(
        self,
        resumes: List[Dict[str, Any]],
        job_pool: List[Dict[str, Any]],
        name_variants: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run batch name-swap fairness evaluation across multiple resumes."""
        profile_reports: List[Dict[str, Any]] = []

        all_max_score_diffs: List[float] = []
        all_mean_score_diffs: List[float] = []
        all_top5_jaccards: List[float] = []
        all_top10_jaccards: List[float] = []
        all_invariance_rates: List[float] = []

        for resume in resumes:
            report = self.evaluate_profile(resume, job_pool, name_variants=name_variants)
            profile_reports.append(report)
            all_max_score_diffs.append(report["max_abs_score_difference"])
            all_mean_score_diffs.append(report["mean_abs_score_difference"])
            all_top5_jaccards.append(report["mean_top5_jaccard_similarity"])
            all_top10_jaccards.append(report["mean_top10_jaccard_similarity"])
            all_invariance_rates.append(report["score_invariance_rate"])

        n = len(profile_reports)

        overall_summary: Dict[str, Any] = {
            "total_profiles_evaluated": n,
            "name_variants_per_profile": len(name_variants or self.synthetic_names),
            "aggregate_score_invariance_rate": round(float(np.mean(all_invariance_rates)), 4) if all_invariance_rates else 1.0,
            "overall_max_score_difference": round(float(max(all_max_score_diffs)), 6) if all_max_score_diffs else 0.0,
            "overall_mean_score_difference": round(float(np.mean(all_mean_score_diffs)), 6) if all_mean_score_diffs else 0.0,
            "overall_mean_top5_jaccard": round(float(np.mean(all_top5_jaccards)), 4) if all_top5_jaccards else 1.0,
            "overall_mean_top10_jaccard": round(float(np.mean(all_top10_jaccards)), 4) if all_top10_jaccards else 1.0,
            "profile_reports": profile_reports,
            "methodology_and_limitations": {
                "scope": "Name-swap perturbation sensitivity testing under identical qualification inputs.",
                "distinction": "Tests algorithmic invariance under surface-level PII perturbation; does not infer real demographic traits or constitute a demographic disparate impact audit.",
                "assumptions": "Equal qualifications, experience, and skills held strictly constant across name substitutions.",
            },
        }

        if n >= 5:
            overall_summary["ci_95_score_difference"] = confidence_interval(
                all_mean_score_diffs, confidence=0.95, method="bootstrap"
            )
        else:
            overall_summary["ci_95_score_difference"] = {
                "note": "Sample size insufficient for bootstrap confidence interval (N < 5)."
            }

        return overall_summary
