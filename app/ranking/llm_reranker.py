"""
app.ranking.llm_reranker
------------------------
LLM-based re-ranker for Phase B:
- Input: Hybrid's top 20 candidate jobs + anonymized resume summary.
- Output: Strict JSON with top 10 ranked jobs:
    job_id, rank, matched_skills, missing_skills, reason
- Strict validation, retry/repair on malformed output, rejection of non-candidate hallucinated job IDs.
- Deterministic: temperature 0.0, fixed seed 42.
- Detailed audit logging: model, prompt_version, token counts, latency.
- Supports both Ollama ('llama3.2:3b') and Gemini (or 'gemini-mock').
"""

import asyncio
from datetime import datetime, timezone
import json
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.ranking.base import BaseRanker, RankingResult
from app.ranking.hybrid import HybridRanker
from app.services.llm_provider import GeminiProvider, OllamaProvider, clean_and_parse_json


PROMPT_VERSION = "v1.1"

RERANKER_PROMPT_TEMPLATE = """Rank the TOP 10 best matching jobs for the candidate from the 20 candidate jobs below (1 is best).
CONSTRAINTS:
1. Identify each job strictly by its label (J1, J2, ..., J20) as job_id. Do NOT invent IDs.
2. Output JSON:
{{"ranked_jobs": [{{"job_id": "J1", "rank": 1, "matched_skills": ["..."], "missing_skills": ["..."], "reason": "1 concise sentence."}}]}}

CANDIDATE:
{resume_summary}

CANDIDATE JOBS (J1 to J20):
{jobs_listing}
"""


def _format_candidate_jobs(jobs: List[Dict[str, Any]]) -> Tuple[str, Dict[str, str], Dict[str, str]]:
    """Format candidate jobs with numbered labels J1 to J20. Return (listing_str, label_to_id, id_to_label)."""
    lines: List[str] = []
    label_to_id: Dict[str, str] = {}
    id_to_label: Dict[str, str] = {}

    for idx, job in enumerate(jobs[:20], 1):
        label = f"J{idx}"
        jid = str(job.get("id") or job.get("external_id") or "")
        label_to_id[label] = jid
        id_to_label[jid] = label

        title = job.get("title") or "Unknown Title"
        skills = job.get("skills") or []
        skills_str = ", ".join(str(s) for s in skills[:6]) if isinstance(skills, list) else str(skills)[:50]
        desc = (job.get("description") or "")[:100].replace("\n", " ").strip()
        lines.append(f"[{label}] Title:{title}|Skills:{skills_str}|Desc:{desc}")

    return "\n".join(lines), label_to_id, id_to_label


def _format_resume_summary(anonymized_resume: Dict[str, Any]) -> str:
    parts: List[str] = []
    skills = anonymized_resume.get("skills") or []
    if skills:
        parts.append(f"Skills: {', '.join(str(s) for s in skills[:20])}")
    if anonymized_resume.get("summary"):
        parts.append(f"Summary: {anonymized_resume['summary'][:250]}")
    exp = anonymized_resume.get("experience") or []
    if exp:
        exp_lines = [f"{e.get('title','')}@{e.get('company','')}" for e in exp[:3]]
        parts.append("Exp: " + "; ".join(exp_lines))
    return "\n".join(parts)


class LLMReranker(BaseRanker):
    """LLM Re-Ranker applying zero-temperature structured inference to Hybrid top 20 candidates."""

    def __init__(
        self,
        name: str = "hybrid_llm_ollama",
        provider_name: str = "ollama",
        hybrid_ranker: Optional[HybridRanker] = None,
        model_name: Optional[str] = None,
        seed: int = 42,
    ):
        super().__init__(name)
        self.provider_name = provider_name
        self.seed = seed
        self.hybrid_ranker = hybrid_ranker or HybridRanker()
        self.prompt_version = PROMPT_VERSION

        if provider_name == "ollama":
            self.model_name = model_name or "llama3.2:3b"
            self.provider = OllamaProvider(model=self.model_name)
        elif provider_name in ("gemini", "gemini-mock"):
            self.model_name = model_name or getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
            self.provider = GeminiProvider(model=self.model_name)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

    def _validate_and_sanitize(
        self,
        raw_ranked_jobs: List[Dict[str, Any]],
        label_to_id: Dict[str, str],
        id_to_label: Dict[str, str],
        top_k: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """Validate returned items, map J1..J20 back to UUIDs, reject invalid labels."""
        sanitized: List[Dict[str, Any]] = []
        hallucinated_count = 0
        repaired_count = 0
        seen_ids: Set[str] = set()

        valid_uuids = set(id_to_label.keys())

        for item in raw_ranked_jobs:
            if not isinstance(item, dict):
                repaired_count += 1
                continue

            raw_jid = str(item.get("job_id") or "").strip()
            # Normalize label format: "J1", "j1", "1", "Job 1", "J-1"
            m = re.search(r"(\d+)", raw_jid)
            normalized_label = f"J{m.group(1)}" if m else raw_jid.upper()

            if normalized_label in label_to_id:
                real_id = label_to_id[normalized_label]
            elif raw_jid in valid_uuids:
                # LLM returned UUID directly instead of label
                real_id = raw_jid
                repaired_count += 1
            else:
                # Hallucinated or unknown label outside J1..J20
                hallucinated_count += 1
                continue

            if real_id in seen_ids:
                continue
            seen_ids.add(real_id)

            matched_skills = item.get("matched_skills") or []
            missing_skills = item.get("missing_skills") or []
            reason = str(item.get("reason") or "Strong overall skill match.")

            sanitized.append({
                "job_id": real_id,
                "rank": len(sanitized) + 1,
                "matched_skills": [str(s) for s in matched_skills] if isinstance(matched_skills, list) else [],
                "missing_skills": [str(s) for s in missing_skills] if isinstance(missing_skills, list) else [],
                "reason": reason,
            })
            if len(sanitized) >= top_k:
                break

        # If LLM returned fewer than top_k, backfill deterministically from candidate pool
        if len(sanitized) < top_k:
            for label, real_id in label_to_id.items():
                if real_id not in seen_ids:
                    sanitized.append({
                        "job_id": real_id,
                        "rank": len(sanitized) + 1,
                        "matched_skills": [],
                        "missing_skills": [],
                        "reason": "Backfilled from Hybrid top candidates.",
                    })
                    repaired_count += 1
                    if len(sanitized) >= top_k:
                        break

        return sanitized, hallucinated_count, repaired_count

    async def _execute_rerank(
        self,
        anonymized_resume: Dict[str, Any],
        candidate_jobs: List[Dict[str, Any]],
        k: int = 10,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Call provider with prompt, retry on malformed JSON, and track metadata."""
        resume_summary = _format_resume_summary(anonymized_resume)
        jobs_listing, label_to_id, id_to_label = _format_candidate_jobs(candidate_jobs)

        prompt = RERANKER_PROMPT_TEMPLATE.format(
            resume_summary=resume_summary,
            jobs_listing=jobs_listing,
        )

        max_attempts = 2
        total_repairs = 0
        total_hallucinations = 0
        last_error = None
        response = None

        t0 = time.perf_counter()

        for attempt in range(max_attempts):
            try:
                # Use generous timeout of 180.0s for CPU inference over 20 items
                if self.provider_name == "ollama":
                    response = await self.provider.generate_json(
                        prompt=prompt,
                        temperature=0.0,
                        max_tokens=1500,
                        seed=self.seed,
                        timeout=180.0,
                    )
                else:
                    response = await self.provider.generate_json(
                        prompt=prompt,
                        temperature=0.0,
                        max_tokens=2048,
                        seed=self.seed,
                        timeout=60.0,
                        experiment_mode=True,
                    )
                data = response.data
                raw_ranked = data.get("ranked_jobs") if isinstance(data, dict) else None
                if not isinstance(raw_ranked, list):
                    # Check if data itself is a list
                    if isinstance(data, list):
                        raw_ranked = data
                    else:
                        raise ValueError("LLM JSON missing 'ranked_jobs' list.")

                sanitized, hall_cnt, rep_cnt = self._validate_and_sanitize(
                    raw_ranked, label_to_id, id_to_label, top_k=k
                )
                total_hallucinations += hall_cnt
                total_repairs += rep_cnt
                latency_ms = round((time.perf_counter() - t0) * 1000, 2)

                metadata = {
                    "provider": response.provider,
                    "model": response.model,
                    "requested_model": getattr(response, "requested_model", response.model),
                    "answered_model": getattr(response, "answered_model", response.model),
                    "quantization": getattr(response, "quantization", "n/a"),
                    "prompt_version": self.prompt_version,
                    "temperature": response.temperature,
                    "max_tokens": response.max_tokens,
                    "seed": self.seed,
                    "seed_requested": getattr(response, "seed_requested", self.seed),
                    "seed_sent": getattr(response, "seed_sent", getattr(response, "seed_requested", self.seed)),
                    "seed_applied": getattr(response, "seed_applied", None),
                    "prompt_tokens": getattr(response, "prompt_tokens", 0),
                    "response_tokens": getattr(response, "response_tokens", 0),
                    "latency_ms": latency_ms,
                    "attempts": attempt + 1,
                    "hallucinated_ids_rejected": total_hallucinations,
                    "repair_count": total_repairs,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                return sanitized, metadata

            except Exception as exc:
                last_error = exc
                total_repairs += 1
                logger.warning(f"Reranker attempt {attempt+1} failed: {exc}. Retrying...")
                await asyncio.sleep(0.5)

        # In experiment mode: a failed call must be recorded as a failed run and never replaced by hybrid output
        logger.error(f"LLM Reranker failed after {max_attempts} attempts: {last_error}.")
        metadata = {
            "provider": self.provider_name,
            "requested_model": self.model_name,
            "answered_model": self.model_name,
            "model": self.model_name,
            "quantization": "n/a",
            "prompt_version": self.prompt_version,
            "temperature": 0.0,
            "max_tokens": 1500 if self.provider_name == "ollama" else 2048,
            "seed": self.seed,
            "seed_requested": self.seed,
            "seed_sent": self.seed,
            "seed_applied": None,
            "prompt_tokens": 0,
            "response_tokens": 0,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "attempts": max_attempts,
            "status": "failed",
            "error_type": type(last_error).__name__,
            "error type": type(last_error).__name__,
            "hallucinated_ids_rejected": total_hallucinations,
            "repair_count": total_repairs,
            "fallback_used": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # In experiment mode, raise RuntimeError or return empty rankings with failed metadata
        raise RuntimeError(f"LLM Reranker failed for provider '{self.provider_name}' after {max_attempts} attempts: {type(last_error).__name__}: {last_error}")

    def rank(
        self,
        anonymized_resume: Dict[str, Any],
        job_pool: List[Dict[str, Any]],
        k: int = 10,
    ) -> RankingResult:
        """Synchronous rank entrypoint running the LLM re-ranker on Hybrid's top 20 candidates."""
        # 1. First get top 20 candidates via HybridRanker
        top20_hybrid = self.hybrid_ranker.rank(anonymized_resume, job_pool, k=20)
        id_to_job = {str(j.get("id") or j.get("external_id") or ""): j for j in job_pool}
        candidate_jobs = [id_to_job[jid] for jid in top20_hybrid.ranked_job_ids if jid in id_to_job]

        # 2. Run LLM re-ranking asynchronously
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                ranked_items, meta = loop.run_until_complete(
                    self._execute_rerank(anonymized_resume, candidate_jobs, k=k)
                )
            else:
                ranked_items, meta = loop.run_until_complete(
                    self._execute_rerank(anonymized_resume, candidate_jobs, k=k)
                )
        except RuntimeError:
            ranked_items, meta = asyncio.run(
                self._execute_rerank(anonymized_resume, candidate_jobs, k=k)
            )

        ranked_job_ids = [item["job_id"] for item in ranked_items]
        # Assign descending score 1.0, 0.9, ... based on rank
        scores = {item["job_id"]: round(1.0 - (idx * 0.05), 4) for idx, item in enumerate(ranked_items)}

        meta["explanations"] = ranked_items

        return RankingResult(
            ranked_job_ids=ranked_job_ids,
            scores=scores,
            method_name=self.name,
            metadata=meta,
        )
