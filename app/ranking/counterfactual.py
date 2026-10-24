"""
app.ranking.counterfactual
--------------------------
Counterfactual Skill-Gap Test (Phase B6):
For a given resume-job pair:
(a) Add suggested missing skills to the candidate resume.
(b) Add an equal number of random skills that the job DOES NOT require.
Re-run scoring for Hybrid Ranker and SBERT-only ranker.
Measure and report score deltas and rank deltas.
"""

import copy
import csv
from pathlib import Path
import random
from typing import Any, Dict, List, Set, Tuple

from app.core.taxonomy import CANONICAL_SKILL_PATTERNS, extract_canonical_skills
from app.ranking.baselines import SbertRanker
from app.ranking.hybrid import HybridRanker


class CounterfactualTester:
    """Evaluates whether acquiring suggested missing skills yields greater ranking improvements than random skills."""

    def __init__(
        self,
        hybrid_ranker: HybridRanker,
        sbert_ranker: SbertRanker,
        seed: int = 42,
    ):
        self.hybrid = hybrid_ranker
        self.sbert = sbert_ranker
        self.seed = seed
        random.seed(seed)
        self.all_canonical_skills = list(CANONICAL_SKILL_PATTERNS.keys())

    def _get_job_skills(self, job: Dict[str, Any]) -> Set[str]:
        title = job.get("title") or ""
        desc = job.get("description") or ""
        raw_skills = job.get("skills") or []
        skills_str = " ".join(str(s) for s in raw_skills) if isinstance(raw_skills, list) else str(raw_skills)
        return {s.lower() for s in extract_canonical_skills(f"{title}\n{skills_str}\n{desc}")}

    def _get_resume_skills(self, resume: Dict[str, Any]) -> Set[str]:
        raw_skills = resume.get("skills") or []
        summary = resume.get("summary") or ""
        raw_text = resume.get("raw_text") or ""
        combined = " ".join([summary, raw_text] + [str(s) for s in raw_skills])
        return {s.lower() for s in extract_canonical_skills(combined)}

    def _sample_random_unrelated_skills(
        self,
        job_skills: Set[str],
        resume_skills: Set[str],
        count: int,
        rng: Optional[random.Random] = None,
    ) -> List[str]:
        """Sample skills that are strictly absent from candidate resume AND not required by target job."""
        candidates = sorted([
            s for s in self.all_canonical_skills
            if s.lower() not in job_skills and s.lower() not in resume_skills
        ])
        if not candidates:
            return []
        sampler = rng if rng is not None else random
        return sampler.sample(candidates, min(count, len(candidates)))

    def run_multi_draw_test(
        self,
        resume: Dict[str, Any],
        target_job: Dict[str, Any],
        suggested_missing_skills: List[str],
        job_pool: List[Dict[str, Any]],
        n_draws: int = 20,
        seed: Optional[int] = 42,
    ) -> Dict[str, Any]:
        """Run counterfactual evaluation with n_draws independent random draws for control skills."""
        import numpy as np

        draw_rng = random.Random(seed) if seed is not None else random.Random(42)

        target_jid = str(target_job.get("id") or target_job.get("external_id") or "")
        job_skills = self._get_job_skills(target_job)
        resume_skills = self._get_resume_skills(resume)

        # Baseline evaluation
        base_hy = self.hybrid.rank(resume, job_pool, k=len(job_pool))
        base_sb = self.sbert.rank(resume, job_pool, k=len(job_pool))

        base_hy_score = base_hy.scores.get(target_jid, 0.0)
        base_sb_score = base_sb.scores.get(target_jid, 0.0)
        base_hy_rank = base_hy.ranked_job_ids.index(target_jid) + 1 if target_jid in base_hy.ranked_job_ids else len(job_pool)
        base_sb_rank = base_sb.ranked_job_ids.index(target_jid) + 1 if target_jid in base_sb.ranked_job_ids else len(job_pool)

        # Condition (a): Add suggested missing skills
        resume_a = copy.deepcopy(resume)
        curr_skills_a = list(resume_a.get("skills") or [])
        curr_skills_a.extend(suggested_missing_skills)
        resume_a["skills"] = list(dict.fromkeys(curr_skills_a))
        resume_a.pop("embedding", None)

        a_hy = self.hybrid.rank(resume_a, job_pool, k=len(job_pool))
        a_sb = self.sbert.rank(resume_a, job_pool, k=len(job_pool))

        a_hy_score = a_hy.scores.get(target_jid, 0.0)
        a_sb_score = a_sb.scores.get(target_jid, 0.0)
        a_hy_rank = a_hy.ranked_job_ids.index(target_jid) + 1 if target_jid in a_hy.ranked_job_ids else len(job_pool)
        a_sb_rank = a_sb.ranked_job_ids.index(target_jid) + 1 if target_jid in a_sb.ranked_job_ids else len(job_pool)

        delta_hy_score_suggested = a_hy_score - base_hy_score
        delta_hy_rank_suggested = base_hy_rank - a_hy_rank
        delta_sb_score_suggested = a_sb_score - base_sb_score
        delta_sb_rank_suggested = base_sb_rank - a_sb_rank

        # Condition (b): Run n_draws random draws with skills absent from both resume & job
        n_missing = max(1, len(suggested_missing_skills))
        random_hy_score_deltas: List[float] = []
        random_hy_rank_deltas: List[int] = []
        random_sb_score_deltas: List[float] = []
        random_sb_rank_deltas: List[int] = []

        all_draw_skills: List[List[str]] = []

        for draw_idx in range(n_draws):
            rnd_skills = self._sample_random_unrelated_skills(job_skills, resume_skills, n_missing, rng=draw_rng)
            all_draw_skills.append(rnd_skills)

            resume_b = copy.deepcopy(resume)
            curr_skills_b = list(resume_b.get("skills") or [])
            curr_skills_b.extend(rnd_skills)
            resume_b["skills"] = list(dict.fromkeys(curr_skills_b))
            resume_b.pop("embedding", None)

            b_hy = self.hybrid.rank(resume_b, job_pool, k=len(job_pool))
            b_sb = self.sbert.rank(resume_b, job_pool, k=len(job_pool))

            b_hy_score = b_hy.scores.get(target_jid, 0.0)
            b_sb_score = b_sb.scores.get(target_jid, 0.0)
            b_hy_rank = b_hy.ranked_job_ids.index(target_jid) + 1 if target_jid in b_hy.ranked_job_ids else len(job_pool)
            b_sb_rank = b_sb.ranked_job_ids.index(target_jid) + 1 if target_jid in b_sb.ranked_job_ids else len(job_pool)

            random_hy_score_deltas.append(b_hy_score - base_hy_score)
            random_hy_rank_deltas.append(base_hy_rank - b_hy_rank)
            random_sb_score_deltas.append(b_sb_score - base_sb_score)
            random_sb_rank_deltas.append(base_sb_rank - b_sb_rank)

        return {
            "target_job_id": target_jid,
            "target_title": target_job.get("title", ""),
            "suggested_skills": suggested_missing_skills,
            "n_draws": n_draws,
            "base_hybrid_score": round(base_hy_score, 4),
            "base_hybrid_rank": base_hy_rank,
            "base_sbert_score": round(base_sb_score, 4),
            "base_sbert_rank": base_sb_rank,
            # Condition A: Suggested missing skills (rank_gain = base_rank - new_rank, positive means improved)
            "suggested_delta_hybrid_score": round(delta_hy_score_suggested, 4),
            "suggested_rank_gain_hybrid": delta_hy_rank_suggested,
            "suggested_delta_sbert_score": round(delta_sb_score_suggested, 4),
            "suggested_rank_gain_sbert": delta_sb_rank_suggested,
            # Condition B: Random control draws (mean ± std)
            "random_delta_hybrid_score_mean": round(float(np.mean(random_hy_score_deltas)), 4),
            "random_delta_hybrid_score_std": round(float(np.std(random_hy_score_deltas)), 4),
            "random_rank_gain_hybrid_mean": round(float(np.mean(random_hy_rank_deltas)), 2),
            "random_rank_gain_hybrid_std": round(float(np.std(random_hy_rank_deltas)), 2),
            "random_delta_sbert_score_mean": round(float(np.mean(random_sb_score_deltas)), 4),
            "random_delta_sbert_score_std": round(float(np.std(random_sb_score_deltas)), 4),
            "random_rank_gain_sbert_mean": round(float(np.mean(random_sb_rank_deltas)), 2),
            "random_rank_gain_sbert_std": round(float(np.std(random_sb_rank_deltas)), 2),
            # Backwards-compatible aliases
            "suggested_delta_hybrid_rank": delta_hy_rank_suggested,
            "suggested_delta_sbert_rank": delta_sb_rank_suggested,
            "random_delta_hybrid_rank_mean": round(float(np.mean(random_hy_rank_deltas)), 2),
            "random_delta_hybrid_rank_std": round(float(np.std(random_hy_rank_deltas)), 2),
            "random_delta_sbert_rank_mean": round(float(np.mean(random_sb_rank_deltas)), 2),
            "random_delta_sbert_rank_std": round(float(np.std(random_sb_rank_deltas)), 2),
        }

    def run_test(
        self,
        resume: Dict[str, Any],
        target_job: Dict[str, Any],
        suggested_missing_skills: List[str],
        job_pool: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Single draw test for backward compatibility."""
        return self.run_multi_draw_test(
            resume, target_job, suggested_missing_skills, job_pool, n_draws=1
        )

    def evaluate_counterfactual_case(
        self,
        resume: Dict[str, Any],
        target_job: Dict[str, Any],
        job_pool: List[Dict[str, Any]],
        suggested_skills: List[str],
        n_control_draws: int = 20,
        evaluate_individual: bool = True,
        evaluate_combinations: bool = True,
    ) -> Dict[str, Any]:
        """
        Evaluate counterfactual interventions with strict exclusions and paired controls:
        - Excludes skills already present in the candidate resume.
        - Evaluates valid skills individually and in combination.
        - Generates privacy-safe candidate/job identifiers.
        - Returns structured case record with valid/excluded status.
        """
        import hashlib
        import itertools
        import numpy as np

        cand_id_raw = str(resume.get("id") or resume.get("candidate_name") or "anonymous")
        anon_cand_id = f"cand_{hashlib.sha256(cand_id_raw.encode('utf-8')).hexdigest()[:12]}"

        target_jid = str(target_job.get("id") or target_job.get("external_id") or "")
        anon_job_id = f"job_{hashlib.sha256(target_jid.encode('utf-8')).hexdigest()[:12]}" if target_jid else "unknown_job"

        job_skills = self._get_job_skills(target_job)
        resume_skills = self._get_resume_skills(resume)

        # Exclusion checks
        already_present_skills = [
            s for s in suggested_skills if s.lower() in resume_skills
        ]
        valid_suggested_skills = [
            s for s in suggested_skills if s.lower() not in resume_skills
        ]

        if not valid_suggested_skills:
            return {
                "is_valid": False,
                "exclusion_reason": "all_target_skills_already_present",
                "candidate_id": anon_cand_id,
                "job_id": anon_job_id,
                "target_title": target_job.get("title", ""),
                "suggested_skills": suggested_skills,
                "already_present_skills": already_present_skills,
                "valid_skills": [],
                "individual_evaluations": [],
                "combination_evaluations": [],
            }

        # Check target job is in pool
        pool_ids = {str(j.get("id") or j.get("external_id") or "") for j in job_pool}
        if target_jid not in pool_ids:
            return {
                "is_valid": False,
                "exclusion_reason": "target_job_not_in_pool",
                "candidate_id": anon_cand_id,
                "job_id": anon_job_id,
                "target_title": target_job.get("title", ""),
                "suggested_skills": suggested_skills,
                "already_present_skills": already_present_skills,
                "valid_skills": valid_suggested_skills,
                "individual_evaluations": [],
                "combination_evaluations": [],
            }

        # Baseline evaluation
        base_hy = self.hybrid.rank(resume, job_pool, k=len(job_pool))
        base_sb = self.sbert.rank(resume, job_pool, k=len(job_pool))
        base_hy_score = base_hy.scores.get(target_jid, 0.0)
        base_sb_score = base_sb.scores.get(target_jid, 0.0)
        base_hy_rank = base_hy.ranked_job_ids.index(target_jid) + 1 if target_jid in base_hy.ranked_job_ids else len(job_pool)
        base_sb_rank = base_sb.ranked_job_ids.index(target_jid) + 1 if target_jid in base_sb.ranked_job_ids else len(job_pool)

        # 1. Individual skill interventions
        individual_evals: List[Dict[str, Any]] = []
        if evaluate_individual:
            for skill in valid_suggested_skills:
                # Add single skill
                res_ind = copy.deepcopy(resume)
                skills_ind = list(res_ind.get("skills") or []) + [skill]
                res_ind["skills"] = list(dict.fromkeys(skills_ind))
                res_ind.pop("embedding", None)

                hy_res = self.hybrid.rank(res_ind, job_pool, k=len(job_pool))
                sb_res = self.sbert.rank(res_ind, job_pool, k=len(job_pool))

                hy_score = hy_res.scores.get(target_jid, 0.0)
                hy_rank = hy_res.ranked_job_ids.index(target_jid) + 1 if target_jid in hy_res.ranked_job_ids else len(job_pool)

                score_delta = hy_score - base_hy_score
                rank_gain = base_hy_rank - hy_rank

                # Paired control draws for single skill
                control_deltas: List[float] = []
                control_rank_gains: List[int] = []
                for _ in range(n_control_draws):
                    rnd = self._sample_random_unrelated_skills(job_skills, resume_skills, 1)
                    res_ctrl = copy.deepcopy(resume)
                    skills_ctrl = list(res_ctrl.get("skills") or []) + rnd
                    res_ctrl["skills"] = list(dict.fromkeys(skills_ctrl))
                    res_ctrl.pop("embedding", None)
                    ctrl_hy = self.hybrid.rank(res_ctrl, job_pool, k=len(job_pool))
                    c_score = ctrl_hy.scores.get(target_jid, 0.0)
                    c_rank = ctrl_hy.ranked_job_ids.index(target_jid) + 1 if target_jid in ctrl_hy.ranked_job_ids else len(job_pool)
                    control_deltas.append(c_score - base_hy_score)
                    control_rank_gains.append(base_hy_rank - c_rank)

                ctrl_score_mean = float(np.mean(control_deltas)) if control_deltas else 0.0
                ctrl_rank_mean = float(np.mean(control_rank_gains)) if control_rank_gains else 0.0

                individual_evals.append({
                    "skill": skill,
                    "baseline_score": round(base_hy_score, 4),
                    "baseline_rank": base_hy_rank,
                    "counterfactual_score": round(hy_score, 4),
                    "counterfactual_rank": hy_rank,
                    "score_delta": round(score_delta, 4),
                    "rank_gain": rank_gain,
                    "control_score_delta_mean": round(ctrl_score_mean, 4),
                    "control_rank_gain_mean": round(ctrl_rank_mean, 2),
                    "lift_over_control_score": round(score_delta - ctrl_score_mean, 4),
                    "lift_over_control_rank": round(rank_gain - ctrl_rank_mean, 2),
                })

        # 2. Combination interventions
        combination_evals: List[Dict[str, Any]] = []
        if evaluate_combinations:
            combos_to_test: List[List[str]] = []
            if len(valid_suggested_skills) > 1:
                combos_to_test.append(valid_suggested_skills)  # Full bundle
            if len(valid_suggested_skills) >= 3:
                # Also test pairs
                combos_to_test.extend([list(c) for c in itertools.combinations(valid_suggested_skills, 2)])

            for combo in combos_to_test:
                res_combo = copy.deepcopy(resume)
                skills_combo = list(res_combo.get("skills") or []) + combo
                res_combo["skills"] = list(dict.fromkeys(skills_combo))
                res_combo.pop("embedding", None)

                hy_combo = self.hybrid.rank(res_combo, job_pool, k=len(job_pool))
                combo_score = hy_combo.scores.get(target_jid, 0.0)
                combo_rank = hy_combo.ranked_job_ids.index(target_jid) + 1 if target_jid in hy_combo.ranked_job_ids else len(job_pool)

                combo_score_delta = combo_score - base_hy_score
                combo_rank_gain = base_hy_rank - combo_rank

                # Paired control draws for combo
                ctrl_combo_deltas: List[float] = []
                ctrl_combo_rank_gains: List[int] = []
                for _ in range(n_control_draws):
                    rnd_combo = self._sample_random_unrelated_skills(job_skills, resume_skills, len(combo))
                    res_c = copy.deepcopy(resume)
                    skills_c = list(res_c.get("skills") or []) + rnd_combo
                    res_c["skills"] = list(dict.fromkeys(skills_c))
                    res_c.pop("embedding", None)
                    c_hy = self.hybrid.rank(res_c, job_pool, k=len(job_pool))
                    cs = c_hy.scores.get(target_jid, 0.0)
                    cr = c_hy.ranked_job_ids.index(target_jid) + 1 if target_jid in c_hy.ranked_job_ids else len(job_pool)
                    ctrl_combo_deltas.append(cs - base_hy_score)
                    ctrl_combo_rank_gains.append(base_hy_rank - cr)

                ctrl_score_mean = float(np.mean(ctrl_combo_deltas)) if ctrl_combo_deltas else 0.0
                ctrl_rank_mean = float(np.mean(ctrl_combo_rank_gains)) if ctrl_combo_rank_gains else 0.0

                combination_evals.append({
                    "skills_combo": combo,
                    "combo_size": len(combo),
                    "baseline_score": round(base_hy_score, 4),
                    "baseline_rank": base_hy_rank,
                    "counterfactual_score": round(combo_score, 4),
                    "counterfactual_rank": combo_rank,
                    "score_delta": round(combo_score_delta, 4),
                    "rank_gain": combo_rank_gain,
                    "control_score_delta_mean": round(ctrl_score_mean, 4),
                    "control_rank_gain_mean": round(ctrl_rank_mean, 2),
                    "lift_over_control_score": round(combo_score_delta - ctrl_score_mean, 4),
                    "lift_over_control_rank": round(combo_rank_gain - ctrl_rank_mean, 2),
                })

        return {
            "is_valid": True,
            "exclusion_reason": None,
            "candidate_id": anon_cand_id,
            "job_id": anon_job_id,
            "target_title": target_job.get("title", ""),
            "suggested_skills": suggested_skills,
            "already_present_skills": already_present_skills,
            "valid_skills": valid_suggested_skills,
            "experiment_seed": self.seed,
            "baseline_hybrid_score": round(base_hy_score, 4),
            "baseline_hybrid_rank": base_hy_rank,
            "individual_evaluations": individual_evals,
            "combination_evaluations": combination_evals,
            "causal_disclaimer": (
                "Counterfactual score deltas reflect algorithmic sensitivity of the ranking function "
                "to skill token additions; they do not establish empirical causal employability "
                "improvement in the labor market."
            ),
        }

    @staticmethod
    def aggregate_counterfactual_evaluations(
        cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate counterfactual cases across candidates and target jobs:
        - Reports valid pairs and excluded cases.
        - Computes paired statistical test and confidence intervals.
        - Enforces explicit causal disclaimer.
        """
        import numpy as np
        from app.ranking.evaluation import confidence_interval, wilcoxon_signed_rank_test

        total_cases = len(cases)
        valid_cases = [c for c in cases if c.get("is_valid", False)]
        excluded_cases = [c for c in cases if not c.get("is_valid", False)]

        exclusion_counts: Dict[str, int] = {}
        for ec in excluded_cases:
            reason = ec.get("exclusion_reason", "unknown")
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1

        all_score_deltas: List[float] = []
        all_rank_gains: List[float] = []
        all_score_lifts: List[float] = []
        all_rank_lifts: List[float] = []

        for vc in valid_cases:
            # Collect from individual evals or combinations
            for ind in vc.get("individual_evaluations", []):
                all_score_deltas.append(ind["score_delta"])
                all_rank_gains.append(float(ind["rank_gain"]))
                all_score_lifts.append(ind["lift_over_control_score"])
                all_rank_lifts.append(float(ind["lift_over_control_rank"]))

            for combo in vc.get("combination_evaluations", []):
                all_score_deltas.append(combo["score_delta"])
                all_rank_gains.append(float(combo["rank_gain"]))
                all_score_lifts.append(combo["lift_over_control_score"])
                all_rank_lifts.append(float(combo["lift_over_control_rank"]))

        n_interventions = len(all_score_deltas)

        # Statistics & Confidence intervals
        stats_summary: Dict[str, Any] = {
            "total_cases": total_cases,
            "valid_cases": len(valid_cases),
            "excluded_cases": len(excluded_cases),
            "exclusion_breakdown": exclusion_counts,
            "total_interventions_evaluated": n_interventions,
        }

        if n_interventions >= 1:
            mean_score_delta = float(np.mean(all_score_deltas))
            mean_rank_gain = float(np.mean(all_rank_gains))
            mean_score_lift = float(np.mean(all_score_lifts))
            mean_rank_lift = float(np.mean(all_rank_lifts))

            stats_summary.update({
                "mean_score_delta": round(mean_score_delta, 4),
                "std_score_delta": round(float(np.std(all_score_deltas)), 4),
                "mean_rank_gain": round(mean_rank_gain, 2),
                "std_rank_gain": round(float(np.std(all_rank_gains)), 2),
                "mean_score_lift_over_control": round(mean_score_lift, 4),
                "mean_rank_lift_over_control": round(mean_rank_lift, 2),
            })

            # 95% Confidence Intervals
            if n_interventions >= 5:
                stats_summary["ci_95_score_delta"] = confidence_interval(
                    all_score_deltas, confidence=0.95, method="bootstrap"
                )
                stats_summary["ci_95_score_lift"] = confidence_interval(
                    all_score_lifts, confidence=0.95, method="bootstrap"
                )
            else:
                stats_summary["ci_95_score_delta"] = {
                    "note": "Sample size insufficient for reliable confidence intervals (N < 5)."
                }

            # Paired Wilcoxon Signed-Rank Test (lift over control vs zero)
            if n_interventions >= 5:
                stats_summary["wilcoxon_test_lift_over_control"] = wilcoxon_signed_rank_test(
                    all_score_lifts,
                    [0.0] * n_interventions,
                )
            else:
                stats_summary["wilcoxon_test_lift_over_control"] = {
                    "note": "Sample size insufficient for Wilcoxon test (N < 5)."
                }
        else:
            stats_summary["note"] = "No valid counterfactual interventions could be evaluated."

        stats_summary["causal_claim_disclaimer"] = (
            "Counterfactual rank deltas measure algorithmic matcher score sensitivity to token/embedding additions "
            "and do not imply real-world causal employability improvement."
        )

        return stats_summary

    def export_csv(self, records: List[Dict[str, Any]], output_path: Path | str) -> Path:
        """Export counterfactual records to CSV."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not records:
            return path
        keys = list(records[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in records:
                writer.writerow(r)
        return path
