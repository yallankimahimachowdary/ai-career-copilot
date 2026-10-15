"""
app.ranking.hybrid
------------------
Hybrid Ranker combining normalized BM25, SBERT, and Skill Overlap scores
with frozen config weights, and CompositeXGBRanker wrapping the product's
production composite scorer + XGBoost pipeline for snapshot evaluation.
"""

import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.ranking.base import BaseRanker, RankingResult
from app.ranking.baselines import BM25Ranker, SbertRanker, SkillOverlapRanker
from scripts.job_snapshot import run_matching_on_snapshot

CONFIG_PATH = Path(__file__).parent / "config.json"


def _min_max_normalize(scores: Dict[str, float]) -> Dict[str, float]:
    """Min-max normalize a dictionary of scores into the [0, 1] range."""
    if not scores:
        return {}
    vals = list(scores.values())
    min_v, max_v = min(vals), max(vals)
    if math_diff := (max_v - min_v):
        return {k: (v - min_v) / math_diff for k, v in scores.items()}
    return {k: 1.0 for k in scores}


# ---------------------------------------------------------------------------
# 1. Hybrid Ranker (Fixed Frozen Weights)
# ---------------------------------------------------------------------------
class HybridRanker(BaseRanker):
    """Combines normalized BM25, SBERT, and Skill Overlap scores using frozen weights."""

    def __init__(
        self,
        name: str = "hybrid",
        config_path: Optional[Path] = None,
        weights: Optional[Dict[str, float]] = None,
        bm25_ranker: Optional[BM25Ranker] = None,
        sbert_ranker: Optional[SbertRanker] = None,
        overlap_ranker: Optional[SkillOverlapRanker] = None,
    ):
        super().__init__(name)
        if weights:
            self.w_bm25 = float(weights.get("bm25", 0.25))
            self.w_sbert = float(weights.get("sbert", 0.45))
            self.w_overlap = float(weights.get("overlap", 0.30))
        else:
            cfg_file = config_path or CONFIG_PATH
            if cfg_file.exists():
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                w = cfg.get("weights", {})
                self.w_bm25 = float(w.get("bm25", 0.25))
                self.w_sbert = float(w.get("sbert", 0.45))
                self.w_overlap = float(w.get("overlap", 0.30))
            else:
                self.w_bm25 = 0.25
                self.w_sbert = 0.45
                self.w_overlap = 0.30

        self.bm25 = bm25_ranker or BM25Ranker()
        self.sbert = sbert_ranker or SbertRanker()
        self.overlap = overlap_ranker or SkillOverlapRanker()

    def rank(
        self,
        anonymized_resume: Dict[str, Any],
        job_pool: List[Dict[str, Any]],
        k: int = 10,
    ) -> RankingResult:
        start_time = time.time()
        if not job_pool:
            return RankingResult([], {}, self.name, {"latency_ms": 0.0})

        # Run constituent rankers across full candidate pool
        r_bm25 = self.bm25.rank(anonymized_resume, job_pool, k=len(job_pool))
        r_sbert = self.sbert.rank(anonymized_resume, job_pool, k=len(job_pool))
        r_overlap = self.overlap.rank(anonymized_resume, job_pool, k=len(job_pool))

        norm_bm25 = _min_max_normalize(r_bm25.scores)
        norm_sbert = _min_max_normalize(r_sbert.scores)
        norm_overlap = _min_max_normalize(r_overlap.scores)

        all_job_ids = list(norm_bm25.keys())
        combined_scores: Dict[str, float] = {}
        for jid in all_job_ids:
            score = (
                self.w_bm25 * norm_bm25.get(jid, 0.0)
                + self.w_sbert * norm_sbert.get(jid, 0.0)
                + self.w_overlap * norm_overlap.get(jid, 0.0)
            )
            combined_scores[jid] = float(score)

        scored_pairs = list(combined_scores.items())
        scored_pairs.sort(key=lambda x: (x[1], -len(x[0]), x[0]), reverse=True)

        ranked_job_ids = [p[0] for p in scored_pairs[:k]]
        all_scores = {p[0]: round(p[1], 4) for p in scored_pairs}

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return RankingResult(
            ranked_job_ids=ranked_job_ids,
            scores=all_scores,
            method_name=self.name,
            metadata={
                "latency_ms": elapsed_ms,
                "weights": {
                    "bm25": self.w_bm25,
                    "sbert": self.w_sbert,
                    "overlap": self.w_overlap,
                },
                "total_candidates": len(job_pool),
            },
        )


# ---------------------------------------------------------------------------
# 2. Composite XGB Ranker (Product Wrapper)
# ---------------------------------------------------------------------------
class CompositeXGBRanker(BaseRanker):
    """Wraps product's composite scorer + TreeSHAP XGBoost matcher for frozen snapshots."""

    def __init__(self, name: str = "composite_xgb"):
        super().__init__(name)

    def rank(
        self,
        anonymized_resume: Dict[str, Any],
        job_pool: List[Dict[str, Any]],
        k: int = 10,
    ) -> RankingResult:
        start_time = time.time()
        if not job_pool:
            return RankingResult([], {}, self.name, {"latency_ms": 0.0})

        # Run snapshot matching via existing run_matching_on_snapshot
        cand_emb = anonymized_resume.get("embedding") or []
        if not cand_emb:
            from app.services.embedding_service import get_sentence_transformer
            text = anonymized_resume.get("summary") or " ".join(anonymized_resume.get("skills", []))
            st_model = get_sentence_transformer()
            cand_emb = st_model.encode(text, convert_to_numpy=True, normalize_embeddings=True).tolist()

        matched_results = run_matching_on_snapshot(
            snapshot_records=job_pool,
            resume_parsed_data=anonymized_resume,
            resume_embedding=cand_emb,
            top_k=k,
        )

        ranked_job_ids = [r["job_id"] for r in matched_results]
        scores = {r["job_id"]: r["final_score"] for r in matched_results}

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return RankingResult(
            ranked_job_ids=ranked_job_ids,
            scores=scores,
            method_name=self.name,
            metadata={
                "latency_ms": elapsed_ms,
                "total_candidates": len(job_pool),
                "matched_count": len(matched_results),
            },
        )
