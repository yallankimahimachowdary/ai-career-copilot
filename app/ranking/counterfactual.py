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
    ) -> List[str]:
        """Sample skills that are strictly absent from candidate resume AND not required by target job."""
        candidates = [
            s for s in self.all_canonical_skills
            if s.lower() not in job_skills and s.lower() not in resume_skills
        ]
        if not candidates:
            return []
        return random.sample(candidates, min(count, len(candidates)))

    def run_multi_draw_test(
        self,
        resume: Dict[str, Any],
        target_job: Dict[str, Any],
        suggested_missing_skills: List[str],
        job_pool: List[Dict[str, Any]],
        n_draws: int = 20,
    ) -> Dict[str, Any]:
        """Run counterfactual evaluation with n_draws independent random draws for control skills."""
        import numpy as np

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
            rnd_skills = self._sample_random_unrelated_skills(job_skills, resume_skills, n_missing)
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
