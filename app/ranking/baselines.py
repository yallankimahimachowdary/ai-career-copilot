"""
app.ranking.baselines
---------------------
Baseline ranking implementations for Phase B:
1. BM25Ranker: RankBM25 (BM25Okapi) over job title, description, and skills using resume text/tokens.
2. SbertRanker: Cosine similarity with dense 384-d sentence-transformers vectors.
3. SkillOverlapRanker: Weighted overlap of canonical skills (required vs nice-to-have, soft skills).
"""

import math
import re
import time
from typing import Any, Dict, List, Set, Tuple
import numpy as np
from rank_bm25 import BM25Okapi

from app.core.taxonomy import (
    COMMON_STOP_WORDS,
    LINKEDIN_CATEGORY_CODES,
    SOFT_SKILLS,
    extract_canonical_skills,
)
from app.ranking.base import BaseRanker, RankingResult
from app.services.embedding_service import embedding_service, get_sentence_transformer


def _tokenize_text(text: str) -> List[str]:
    """Tokenize and filter stop words and punctuation for BM25."""
    if not text:
        return []
    tokens = re.findall(r"\b[a-zA-Z0-9+#./]{2,30}\b", text.lower())
    return [
        t for t in tokens
        if t not in COMMON_STOP_WORDS and t.upper() not in LINKEDIN_CATEGORY_CODES
    ]


# ---------------------------------------------------------------------------
# 1. BM25 Ranker
# ---------------------------------------------------------------------------
class BM25Ranker(BaseRanker):
    """BM25 ranking baseline over job title, description, and skills."""

    def __init__(self, name: str = "bm25"):
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

        # Build corpus tokens
        corpus: List[List[str]] = []
        job_ids: List[str] = []

        for job in job_pool:
            jid = str(job.get("id") or job.get("external_id") or "")
            job_ids.append(jid)

            title = job.get("title") or ""
            desc = job.get("description") or ""
            skills = job.get("skills") or []
            if isinstance(skills, list):
                skills_str = " ".join(str(s) for s in skills)
            else:
                skills_str = str(skills)

            combined_text = f"{title} {title} {skills_str} {desc}"
            corpus.append(_tokenize_text(combined_text))

        bm25 = BM25Okapi(corpus)

        # Build query tokens from resume
        query_parts: List[str] = []
        if anonymized_resume.get("raw_text"):
            query_parts.append(anonymized_resume["raw_text"])
        if anonymized_resume.get("summary"):
            query_parts.append(anonymized_resume["summary"])
        if anonymized_resume.get("skills"):
            query_parts.append(" ".join(anonymized_resume["skills"]))

        query_tokens = _tokenize_text(" ".join(query_parts))
        if not query_tokens:
            query_tokens = ["software", "developer"]

        doc_scores = bm25.get_scores(query_tokens)

        # Associate scores and sort deterministically
        scored_pairs: List[Tuple[str, float]] = [
            (job_ids[i], float(doc_scores[i])) for i in range(len(job_ids))
        ]
        # Sort descending by score, tie-break by job_id ascending
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
                "total_candidates": len(job_pool),
                "query_token_count": len(query_tokens),
            },
        )


# ---------------------------------------------------------------------------
# 2. SBERT-only Ranker
# ---------------------------------------------------------------------------
class SbertRanker(BaseRanker):
    """Dense semantic vector similarity using sentence-transformers (all-MiniLM-L6-v2, 384 dim)."""

    def __init__(self, name: str = "sbert"):
        super().__init__(name)

    def _get_resume_text(self, anonymized_resume: Dict[str, Any]) -> str:
        parts: List[str] = []
        if anonymized_resume.get("summary"):
            parts.append(anonymized_resume["summary"])
        if anonymized_resume.get("skills"):
            parts.append("Skills: " + ", ".join(anonymized_resume["skills"]))
        for exp in anonymized_resume.get("experience", []):
            if isinstance(exp, dict):
                t = exp.get("title", "")
                c = exp.get("company", "")
                d = exp.get("description", "")
                if isinstance(d, list):
                    d = " ".join(d)
                parts.append(f"{t} at {c}. {d}")
        if not parts and anonymized_resume.get("raw_text"):
            parts.append(anonymized_resume["raw_text"][:2000])
        return "\n".join(parts)

    def _get_job_text(self, job: Dict[str, Any]) -> str:
        parts: List[str] = []
        if job.get("title"):
            parts.append(f"Job Title: {job['title']}")
        if job.get("company"):
            parts.append(f"Company: {job['company']}")
        skills = job.get("skills")
        if skills:
            if isinstance(skills, list):
                parts.append("Required Skills: " + ", ".join(str(s) for s in skills))
            else:
                parts.append(f"Required Skills: {skills}")
        if job.get("description"):
            parts.append(f"Description: {job['description'][:2000]}")
        return "\n".join(parts)

    def rank(
        self,
        anonymized_resume: Dict[str, Any],
        job_pool: List[Dict[str, Any]],
        k: int = 10,
    ) -> RankingResult:
        start_time = time.time()
        if not job_pool:
            return RankingResult([], {}, self.name, {"latency_ms": 0.0})

        st_model = get_sentence_transformer()

        # Compute or use pre-existing candidate embedding
        if "embedding" in anonymized_resume and anonymized_resume["embedding"]:
            cand_emb = np.array(anonymized_resume["embedding"], dtype=np.float32)
        else:
            resume_text = self._get_resume_text(anonymized_resume)
            cand_emb = st_model.encode(resume_text, convert_to_numpy=True, normalize_embeddings=True)

        norm_c = np.linalg.norm(cand_emb)
        if norm_c > 0:
            cand_emb = cand_emb / norm_c

        # Batch encode job texts if not pre-embedded
        job_texts: List[str] = []
        job_ids: List[str] = []
        precomputed_embs: List[Optional[np.ndarray]] = []

        for job in job_pool:
            jid = str(job.get("id") or job.get("external_id") or "")
            job_ids.append(jid)
            if "embedding" in job and job["embedding"]:
                emb = np.array(job["embedding"], dtype=np.float32)
                n = np.linalg.norm(emb)
                precomputed_embs.append(emb / n if n > 0 else emb)
                job_texts.append("")
            else:
                precomputed_embs.append(None)
                job_texts.append(self._get_job_text(job))

        # Check if we need batch encoding
        indices_to_encode = [i for i, emb in enumerate(precomputed_embs) if emb is None]
        if indices_to_encode:
            texts_to_encode = [job_texts[i] for i in indices_to_encode]
            batch_vectors = st_model.encode(
                texts_to_encode,
                batch_size=64,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            for idx, vec in zip(indices_to_encode, batch_vectors):
                precomputed_embs[idx] = vec

        # Compute cosine similarities
        job_matrix = np.vstack(precomputed_embs)
        similarities = np.dot(job_matrix, cand_emb)

        scored_pairs: List[Tuple[str, float]] = [
            (job_ids[i], float(similarities[i])) for i in range(len(job_ids))
        ]
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
                "total_candidates": len(job_pool),
                "embedding_dimension": int(cand_emb.shape[0]),
            },
        )


# ---------------------------------------------------------------------------
# 3. Skill Overlap Ranker
# ---------------------------------------------------------------------------
class SkillOverlapRanker(BaseRanker):
    """Weighted overlap of canonical skills (required vs nice-to-have, soft skills) with coverage-aware scoring."""

    def __init__(
        self,
        name: str = "overlap",
        must_have_weight: float = 1.0,
        nice_to_have_weight: float = 0.5,
        soft_skill_weight: float = 0.25,
        min_skills: int = 4,
    ):
        super().__init__(name)
        self.must_have_weight = must_have_weight
        self.nice_to_have_weight = nice_to_have_weight
        self.soft_skill_weight = soft_skill_weight
        self.min_skills = min_skills

    def _extract_candidate_canonical(self, anonymized_resume: Dict[str, Any]) -> Set[str]:
        raw_skills = anonymized_resume.get("skills") or []
        summary = anonymized_resume.get("summary") or ""
        raw_text = anonymized_resume.get("raw_text") or ""
        combined = " ".join([summary, raw_text] + [str(s) for s in raw_skills])
        return set(s.lower() for s in extract_canonical_skills(combined))

    def _extract_job_skills(self, job: Dict[str, Any]) -> Tuple[Set[str], Set[str], Set[str]]:
        """Return (must_have_hard, nice_to_have_hard, soft_skills)."""
        title = job.get("title") or ""
        desc = job.get("description") or ""
        raw_skills = job.get("skills") or []
        if isinstance(raw_skills, list):
            skills_str = " ".join(str(s) for s in raw_skills)
        else:
            skills_str = str(raw_skills)

        all_found = set(s.lower() for s in extract_canonical_skills(f"{title}\n{skills_str}\n{desc}"))

        soft_found = {s for s in all_found if s in SOFT_SKILLS}
        hard_found = all_found - soft_found

        desc_lower = desc.lower()
        must_keywords = ["requirements", "qualifications", "must have", "required skills", "minimum"]
        nice_keywords = ["preferred", "nice to have", "plus", "bonus", "good to have"]

        has_must = any(k in desc_lower for k in must_keywords)
        has_nice = any(k in desc_lower for k in nice_keywords)

        if has_must and has_nice:
            must_hard: Set[str] = set()
            nice_hard: Set[str] = set()
            for s in hard_found:
                if any(k in desc_lower and s in desc_lower[desc_lower.find(k):] for k in nice_keywords):
                    nice_hard.add(s)
                else:
                    must_hard.add(s)
            return must_hard, nice_hard, soft_found

        # Default split: first half or all are must-have
        return hard_found, set(), soft_found

    def rank(
        self,
        anonymized_resume: Dict[str, Any],
        job_pool: List[Dict[str, Any]],
        k: int = 10,
    ) -> RankingResult:
        start_time = time.time()
        if not job_pool:
            return RankingResult([], {}, self.name, {"latency_ms": 0.0})

        cand_skills = self._extract_candidate_canonical(anonymized_resume)

        scored_entries: List[Dict[str, Any]] = []

        for job in job_pool:
            jid = str(job.get("id") or job.get("external_id") or "")
            must_hard, nice_hard, soft_found = self._extract_job_skills(job)

            # Compute weighted matching
            must_matched = len(cand_skills.intersection(must_hard))
            nice_matched = len(cand_skills.intersection(nice_hard))
            soft_matched = len(cand_skills.intersection(soft_found))

            total_possible = (
                len(must_hard) * self.must_have_weight
                + len(nice_hard) * self.nice_to_have_weight
                + len(soft_found) * self.soft_skill_weight
            )

            # Coverage-aware denominator: prevents sparse jobs with 1-2 skills from reaching an inflated 1.00
            effective_denominator = max(total_possible, self.min_skills * self.must_have_weight)

            if effective_denominator > 0:
                score = (
                    must_matched * self.must_have_weight
                    + nice_matched * self.nice_to_have_weight
                    + soft_matched * self.soft_skill_weight
                ) / effective_denominator
            else:
                score = 0.0

            scored_entries.append({
                "job_id": jid,
                "score": float(score),
                "must_matched": must_matched,
                "total_possible": total_possible,
            })

        # Deterministic tie-breaking: score desc, must_matched desc, total_possible desc, job_id desc
        scored_entries.sort(
            key=lambda x: (x["score"], x["must_matched"], x["total_possible"], x["job_id"]),
            reverse=True,
        )

        ranked_job_ids = [e["job_id"] for e in scored_entries[:k]]
        all_scores = {e["job_id"]: round(e["score"], 4) for e in scored_entries}

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return RankingResult(
            ranked_job_ids=ranked_job_ids,
            scores=all_scores,
            method_name=self.name,
            metadata={
                "latency_ms": elapsed_ms,
                "candidate_skills_count": len(cand_skills),
                "total_candidates": len(job_pool),
            },
        )
