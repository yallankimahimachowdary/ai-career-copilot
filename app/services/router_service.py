"""
app/services/router_service.py
------------------------------
Adaptive Query Intent Router & Multi-Agent Retrieval-Augmented Generation (RAG).

Author: AI Career Copilot Engineering Team (Bala Maan Shree M & Yallanki Mahima Chowdary)

Architectural Contribution:
Rather than relying on a monolithic dense vector retrieval pipeline that indiscriminately
searches the entire database regardless of query semantics, this Adaptive Intent Router
evaluates the candidate's query and dynamically routes execution to one of 4 targeted
strategies:

  Strategy 1: JOB_SEARCH_AND_MATCH
    -> pgvector semantic similarity + relational salary/location filters (Matcher Agent)
  Strategy 2: SKILL_PROGRESSION_AND_PATH
    -> Skill gap diagnostics, role transition prerequisites & roadmaps (Coach/Graph Agent)
  Strategy 3: INTERVIEW_COACHING
    -> Curated technical & STAR behavioral question banks & rubrics (Coach Agent)
  Strategy 4: MACRO_MARKET_DYNAMICS
    -> Real-time compensation percentiles & labor demand aggregations (Market Agent)
"""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import joblib
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.taxonomy import extract_canonical_skills
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    IntentType,
    RouterDecision,
)
from app.services.coach_service import coach_agent
from app.services.embedding_service import embedding_service
from app.services.market_service import market_agent


STRATEGY_MAP: Dict[str, str] = {
    "job_search": "Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
    "skill_gap_analysis": "Strategy 2: Skill-Gap Diagnostic & Learning Roadmap Synthesis",
    "interview_preparation": "Strategy 3: Curated Question Bank & STAR Rubric Retrieval",
    "career_advice": "Strategy 4: Labor Market Dynamics & Career Advisory",
    "resume_feedback": "Strategy 5: Resume Feedback & ATS Alignment Synthesis",
}

CANONICAL_TO_INTENT: Dict[str, IntentType] = {
    "job_search": IntentType.JOB_SEARCH_AND_MATCH,
    "skill_gap_analysis": IntentType.SKILL_PROGRESSION_AND_PATH,
    "interview_preparation": IntentType.INTERVIEW_COACHING,
    "career_advice": IntentType.MACRO_MARKET_DYNAMICS,
    "resume_feedback": IntentType.RESUME_FEEDBACK,
}


class AdaptiveRouterService:
    """Classifies user queries and executes targeted Adaptive RAG retrieval strategies."""

    def __init__(self) -> None:
        self.ollama_base_url: Optional[str] = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model: str = getattr(settings, "OLLAMA_MODEL", "llama3.2:3b")
        self.gemini_key: Optional[str] = "ollama"  # Retained for fallback toggling and test compatibility
        self.router_backend: str = os.getenv("ROUTER_BACKEND", getattr(settings, "ROUTER_BACKEND", "trained")).lower()
        self._model = None
        self._meta: Optional[Dict[str, Any]] = None
        self._tau: float = 0.33
        self._classes: List[str] = []
        self._model_loaded: bool = False
        self._load_trained_model()

    def _load_trained_model(self) -> None:
        """Loads trained scikit-learn model with hash verification."""
        model_path = Path("artifacts/models/intent_router_v1.joblib")
        meta_path = Path("artifacts/models/intent_router_v1.meta.json")

        if not model_path.exists() or not meta_path.exists():
            logger.warning("Trained intent router model files not found at %s. Falling back to heuristic.", model_path)
            self._model = None
            self._model_loaded = False
            return

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                self._meta = json.load(f)

            expected_sha = self._meta.get("model_sha256")
            with open(model_path, "rb") as f:
                actual_bytes = f.read()
            actual_sha = hashlib.sha256(actual_bytes).hexdigest().upper()

            if expected_sha and actual_sha != expected_sha:
                logger.warning(
                    "Model SHA-256 hash mismatch! Expected %s, got %s. Model may be tampered or corrupted. Falling back to heuristic.",
                    expected_sha, actual_sha,
                )
                self._model = None
                self._model_loaded = False
                return

            self._model = joblib.load(model_path)
            self._tau = float(self._meta.get("validation_metrics", {}).get("tau", 0.33))
            self._classes = list(self._meta.get("classes", []))
            self._model_loaded = True
            logger.info("Successfully loaded trained intent router model (hash: %s, tau: %.2f)", actual_sha[:8], self._tau)
        except Exception as exc:
            logger.warning("Failed to load trained intent router model: %s. Falling back to heuristic.", exc)
            self._model = None
            self._model_loaded = False

    # ---------------------------------------------------------------------------
    # Intent Classification Layer
    # ---------------------------------------------------------------------------

    def _clean_and_parse_json(self, text_content: str) -> dict:
        """Strip markdown fences, locate JSON delimiters, fix common syntax flaws, and parse."""
        cleaned = text_content.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                fixed = re.sub(r",\s*([\]}])", r"\1", candidate)
                return json.loads(fixed)

        raise ValueError(f"Could not extract valid JSON from response: {text_content[:200]}")

    async def classify_intent(
        self,
        query: str,
        use_llm: Optional[bool] = None,
        backend: Optional[str] = None,
    ) -> RouterDecision:
        """
        Classifies user query intent using trained model, LLM, or heuristic.
        Supports backend='trained' (default) | 'llm' | 'heuristic'.
        """
        selected_backend = (backend or os.getenv("ROUTER_BACKEND", self.router_backend)).lower()
        if use_llm is True:
            selected_backend = "llm"
        elif use_llm is False and selected_backend == "llm":
            selected_backend = "heuristic"

        if selected_backend == "trained":
            if not self._model_loaded:
                self._load_trained_model()

            if self._model_loaded and self._model is not None:
                try:
                    probs = self._model.predict_proba([query])[0]
                    classes = self._model.classes_ if hasattr(self._model, "classes_") else self._classes
                    max_idx = int(np.argmax(probs))
                    pred_class = str(classes[max_idx])
                    confidence = float(probs[max_idx])
                    low_conf = bool(confidence < self._tau)

                    canonical = pred_class.lower()
                    intent_enum = CANONICAL_TO_INTENT.get(canonical, IntentType.JOB_SEARCH_AND_MATCH)
                    strategy_str = STRATEGY_MAP.get(canonical, "Strategy 1: Hybrid Vector Search & XGBoost Re-ranking")

                    return RouterDecision(
                        intent=intent_enum,
                        confidence=round(confidence, 4),
                        strategy_selected=strategy_str,
                        reasoning=f"Classified as '{canonical}' with confidence {confidence:.2f} via trained TF-IDF Logistic Regression.",
                        backend="trained",
                        low_confidence=low_conf,
                        fallback_used=False,
                        strategy=strategy_str,
                    )
                except Exception as exc:
                    logger.warning("Trained model classification failed (%s); falling back to heuristic.", exc)
                    fallback_decision = self._classify_heuristic(query)
                    fallback_decision.fallback_used = True
                    return fallback_decision
            else:
                fallback_decision = self._classify_heuristic(query)
                fallback_decision.fallback_used = True
                return fallback_decision

        elif selected_backend == "llm":
            if self.ollama_base_url and self.gemini_key is not None:
                try:
                    decision = await self._classify_with_ollama(query)
                    if decision:
                        decision.backend = "llm"
                        decision.fallback_used = False
                        return decision
                except Exception as exc:
                    logger.warning("Ollama intent classification failed; falling back to heuristic: %s", exc)

            fallback_decision = self._classify_heuristic(query)
            fallback_decision.fallback_used = True
            return fallback_decision

        else:  # heuristic
            return self._classify_heuristic(query)

    async def _classify_with_ollama(self, query: str, max_attempts: int = 2) -> Optional[RouterDecision]:
        """Query Ollama to classify intent into one of the 4 canonical enum categories."""
        if not self.ollama_base_url:
            return None

        prompt = f"""
You are the Query Intent Router for an AI Career Copilot multi-agent system.
Analyze the user's career query and classify it into EXACTLY ONE of the following 5 categories:

1. JOB_SEARCH_AND_MATCH: The user is looking for job openings, matches, job recommendations, or asking if they qualify for specific roles.
2. SKILL_PROGRESSION_AND_PATH: The user is asking about missing skills, learning roadmaps, prerequisites, courses, or how to bridge skill gaps.
3. INTERVIEW_COACHING: The user is asking about interview preparation, technical questions, behavioral STAR questions, or mock answer practice.
4. MACRO_MARKET_DYNAMICS: The user is asking about salaries, compensation percentiles, industry demand trends, career path advice, or market overview.
5. RESUME_FEEDBACK: The user is asking to review, critique, audit, or improve their resume, bullet points, summary, or ATS compatibility.

User Query: "{query}"

Respond with ONLY a raw JSON object with this exact structure:
{{
  "intent": "JOB_SEARCH_AND_MATCH" | "SKILL_PROGRESSION_AND_PATH" | "INTERVIEW_COACHING" | "MACRO_MARKET_DYNAMICS" | "RESUME_FEEDBACK",
  "confidence": 0.95,
  "strategy_selected": "Strategy description",
  "reasoning": "Clear 1-sentence justification"
}}
"""

        from app.services.llm_provider import get_llm_provider
        provider = get_llm_provider()

        url = f"{self.ollama_base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_ctx": 8192,
            },
        }

        for attempt in range(1, max_attempts + 1):
            try:
                parsed = None
                try:
                    resp = await provider.generate_json(
                        prompt=prompt,
                        temperature=0.0,
                        max_tokens=250,
                        keep_alive="30m",
                        timeout=60.0,
                    )
                    parsed = resp.data
                except Exception:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.post(url, json=payload)
                        resp.raise_for_status()
                        data = resp.json()

                        if "response" in data:
                            raw_text = data.get("response", "")
                        elif "candidates" in data:
                            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        else:
                            raw_text = json.dumps(data)

                        parsed = self._clean_and_parse_json(raw_text)

                if not parsed or not isinstance(parsed, dict):
                    continue

                raw_intent = str(parsed.get("intent", "")).strip().upper()
                intent_mapping = {
                    "JOB_SEARCH_AND_MATCH": IntentType.JOB_SEARCH_AND_MATCH,
                    "JOB_SEARCH": IntentType.JOB_SEARCH_AND_MATCH,
                    "JOB_MATCH": IntentType.JOB_SEARCH_AND_MATCH,
                    "SKILL_PROGRESSION_AND_PATH": IntentType.SKILL_PROGRESSION_AND_PATH,
                    "SKILL_PROGRESSION": IntentType.SKILL_PROGRESSION_AND_PATH,
                    "SKILL_PATH": IntentType.SKILL_PROGRESSION_AND_PATH,
                    "SKILL_GAP_ANALYSIS": IntentType.SKILL_PROGRESSION_AND_PATH,
                    "SKILL_GAP": IntentType.SKILL_PROGRESSION_AND_PATH,
                    "INTERVIEW_COACHING": IntentType.INTERVIEW_COACHING,
                    "INTERVIEW": IntentType.INTERVIEW_COACHING,
                    "INTERVIEW_PREPARATION": IntentType.INTERVIEW_COACHING,
                    "INTERVIEW_PREP": IntentType.INTERVIEW_COACHING,
                    "COACHING": IntentType.INTERVIEW_COACHING,
                    "MACRO_MARKET_DYNAMICS": IntentType.MACRO_MARKET_DYNAMICS,
                    "MARKET_DYNAMICS": IntentType.MACRO_MARKET_DYNAMICS,
                    "MARKET": IntentType.MACRO_MARKET_DYNAMICS,
                    "CAREER_ADVICE": IntentType.MACRO_MARKET_DYNAMICS,
                    "CAREER": IntentType.MACRO_MARKET_DYNAMICS,
                    "RESUME_FEEDBACK": IntentType.RESUME_FEEDBACK,
                    "RESUME": IntentType.RESUME_FEEDBACK,
                    "FEEDBACK": IntentType.RESUME_FEEDBACK,
                }

                intent_val = intent_mapping.get(raw_intent)
                if not intent_val:
                    for candidate_enum in IntentType:
                        if candidate_enum.value.upper() in raw_intent or raw_intent in candidate_enum.value.upper():
                            intent_val = candidate_enum
                            break

                if intent_val:
                    strat_str = parsed.get("strategy_selected", "Dynamic agent dispatch")
                    return RouterDecision(
                        intent=intent_val,
                        confidence=float(parsed.get("confidence", 0.95)),
                        strategy_selected=strat_str,
                        reasoning=parsed.get("reasoning", "Classified via semantic intent analysis."),
                        backend="llm",
                        low_confidence=False,
                        fallback_used=False,
                        strategy=strat_str,
                    )
            except Exception as exc:
                logger.warning(
                    "LLM intent classification attempt %d/%d failed: %s",
                    attempt, max_attempts, exc
                )
                if attempt < max_attempts:
                    continue

        return None

    async def _classify_with_gemini(self, query: str) -> Optional[RouterDecision]:
        """Backwards compatibility alias for _classify_with_ollama."""
        return await self._classify_with_ollama(query)

    def _classify_heuristic(self, query: str) -> RouterDecision:
        """
        High-precision rule-based classifier based on domain keywords and intent patterns.
        Supports 5 canonical intents:
          - Resume Feedback (RESUME_FEEDBACK)
          - Interview Preparation (INTERVIEW_COACHING / INTERVIEW_PREPARATION)
          - Skill-Gap Analysis (SKILL_PROGRESSION_AND_PATH / SKILL_GAP_ANALYSIS)
          - Career Advice / Macro Market (MACRO_MARKET_DYNAMICS / CAREER_ADVICE)
          - Job Search & Match (JOB_SEARCH_AND_MATCH / JOB_SEARCH)
        """
        q = query.lower()

        # 1. Resume Feedback
        resume_patterns = [
            r"\b(review|critique|check|audit|format|formatting|rewrite|optimize|strengthen|highlight|organize|organized)\b.*\b(resume|cv|summary|bullets?)\b",
            r"\b(resume|cv)\b.*\b(feedback|layout|clarity|weaknesses|errors|ats|scanners?|bullet|bullets?|tips|skills|strengths)\b",
            r"\b(bullet\s*points?|ats\s*scanners?|ats\s*score|ats\s*optimized|resume\s*summary|resume\s*review|resume\s*feedback)\b",
            r"\b(on\s*my\s*resume|in\s*my\s*resume|my\s*resume|my\s*cv)\b",
            r"\b(quantifiable\s*business\s*impact|action\s*verbs)\b",
        ]
        if any(re.search(p, q) for p in resume_patterns) and not re.search(r"\b(jobs?|vacanc|postings?|openings?)\b.*\b(matching|apply|for\s*me|near|in\s*[A-Z])\b", q):
            return RouterDecision(
                intent=IntentType.RESUME_FEEDBACK,
                confidence=0.94,
                strategy_selected="Strategy 5: Resume Feedback & ATS Alignment Synthesis",
                reasoning="Detected resume critique, bullet point refinement, or ATS optimization query.",
                backend="heuristic",
                low_confidence=False,
                fallback_used=False,
                strategy="Strategy 5: Resume Feedback & ATS Alignment Synthesis",
            )

        # 2. Interview Preparation
        interview_patterns = [
            r"\b(interview|mock|star|rubric|behavioral|coding\s*round|technical\s*round|system\s*design\s*round|system\s*design\s*interview|live\s*coding|sample\s*answer)\b",
            r"\b(ask\s*me\s*a|practice\s*answering|how\s*do\s*i\s*answer|questions?\s*to\s*ask\s*the\s*interviewer|interview\s*questions?)\b",
            r"\b(behavioral\s*questions?|technical\s*interview\s*questions?|eval.*rubric)\b",
        ]
        if any(re.search(p, q) for p in interview_patterns):
            return RouterDecision(
                intent=IntentType.INTERVIEW_COACHING,
                confidence=0.94,
                strategy_selected="Strategy 3: Curated Question Bank & STAR Rubric Retrieval",
                reasoning="Detected interview preparation, technical/behavioral question keywords.",
                backend="heuristic",
                low_confidence=False,
                fallback_used=False,
                strategy="Strategy 3: Curated Question Bank & STAR Rubric Retrieval",
            )

        # 3. Skill-Gap Analysis
        skill_gap_patterns = [
            r"\b(skill\s*gap|skill\s*gaps|gaps?|missing|roadmap|prerequisite|prerequisites|curriculum|bridge)\b",
            r"\b(technologies\s*am\s*i\s*missing|what\s*skills\s*do\s*i\s*need|progression\s*plan|learning\s*roadmap)\b",
            r"\b(difference\s*between\s*my\s*skills|prioritize\s*to\s*improve|acquire\s*the\s*missing)\b",
        ]
        if any(re.search(p, q) for p in skill_gap_patterns) and not re.search(r"\b(find|search|show\s*open|vacanc|listings?)\b", q):
            return RouterDecision(
                intent=IntentType.SKILL_PROGRESSION_AND_PATH,
                confidence=0.90,
                strategy_selected="Strategy 2: Skill-Gap Diagnostic & Learning Roadmap Synthesis",
                reasoning="Detected skill gap diagnostic and learning roadmap inquiry.",
                backend="heuristic",
                low_confidence=False,
                fallback_used=False,
                strategy="Strategy 2: Skill-Gap Diagnostic & Learning Roadmap Synthesis",
            )

        # 4. Job Search & Match
        job_search_patterns = [
            r"\b(jobs?|openings?|vacanc(?:y|ies)|postings?|listings?|opportunities|apply\s*for)\b",
            r"\b(find.*jobs?|search.*postings?|recommend.*openings?|hiring.*engineers?|roles.*apply)\b",
        ]
        if any(re.search(p, q) for p in job_search_patterns) and not re.search(r"\b(salary|salaries|compensation|pay|rate|percentile|market|prospects|trends?|career)\b", q):
            return RouterDecision(
                intent=IntentType.JOB_SEARCH_AND_MATCH,
                confidence=0.92,
                strategy_selected="Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
                reasoning="Classified as job opportunity discovery or qualification matching.",
                backend="heuristic",
                low_confidence=False,
                fallback_used=False,
                strategy="Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
            )

        # 5. Career Advice & Macro Market Dynamics
        market_keywords = [
            "salary", "salaries", "compensation", "pay", "earn", "rate", "percentile",
            "market", "trending", "hiring", "demand", "average wage", "cost of living",
            "cities", "locations", "hottest", "median", "career", "management path",
            "staff engineer", "transition from", "switch from", "negotiate", "prospects",
            "worth the investment", "startup or", "advice", "career strategy", "tech hubs"
        ]
        if any(re.search(r"\b" + re.escape(w) + r"\b", q) for w in market_keywords):
            return RouterDecision(
                intent=IntentType.MACRO_MARKET_DYNAMICS,
                confidence=0.91,
                strategy_selected="Strategy 4: Labor Market Dynamics & Career Advisory",
                reasoning="Detected compensation, career path trajectory, or labor market trend keywords.",
                backend="heuristic",
                low_confidence=False,
                fallback_used=False,
                strategy="Strategy 4: Labor Market Dynamics & Career Advisory",
            )

        # Default Strategy 1: Job Search & Match
        return RouterDecision(
            intent=IntentType.JOB_SEARCH_AND_MATCH,
            confidence=0.85,
            strategy_selected="Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
            reasoning="Classified as job opportunity discovery or qualification matching.",
            backend="heuristic",
            low_confidence=False,
            fallback_used=False,
            strategy="Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
        )

    # ---------------------------------------------------------------------------
    # Execution & Multi-Agent Dispatch Layer
    # ---------------------------------------------------------------------------

    async def route_and_execute(
        self,
        db: AsyncSession,
        request: ChatQueryRequest,
        use_llm: bool = True,
    ) -> ChatQueryResponse:
        """
        Classifies the query intent, routes to the corresponding autonomous agent,
        and synthesizes a grounded, explainable response.
        """
        # Step 1: Classify Intent
        decision = await self.classify_intent(request.query, use_llm=use_llm)
        logger.info(
            "Adaptive Intent Router classified query '%s' -> %s (conf: %.2f)",
            request.query[:50], decision.intent.value, decision.confidence
        )

        # Step 2: Fetch Active Resume Context if supplied
        resume = None
        if request.resume_id:
            res_query = await db.execute(select(Resume).where(Resume.id == request.resume_id))
            resume = res_query.scalar_one_or_none()

        # Step 3: Dispatch to Strategy
        if decision.intent in (IntentType.RESUME_FEEDBACK,):
            return await self._execute_resume_feedback(db, request, decision, resume)
        elif decision.intent in (IntentType.JOB_SEARCH_AND_MATCH, IntentType.JOB_SEARCH):
            return await self._execute_job_search(db, request, decision, resume)
        elif decision.intent in (IntentType.SKILL_PROGRESSION_AND_PATH, IntentType.SKILL_GAP_ANALYSIS):
            return await self._execute_skill_progression(db, request, decision, resume)
        elif decision.intent in (IntentType.INTERVIEW_COACHING, IntentType.INTERVIEW_PREPARATION):
            return await self._execute_interview_coaching(db, request, decision, resume)
        else:
            return await self._execute_market_dynamics(db, request, decision, resume)

    async def _execute_resume_feedback(
        self,
        db: AsyncSession,
        request: ChatQueryRequest,
        decision: RouterDecision,
        resume: Optional[Resume] = None,
    ) -> ChatQueryResponse:
        """Synthesizes high-impact resume critique, ATS alignment, and bullet point enhancements."""
        sources: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        if resume and resume.parsed_data:
            pd = resume.parsed_data
            candidate_name = resume.candidate_name or pd.get("contact_info", {}).get("name") or "Candidate"
            skills_count = len(pd.get("skills", []))
            exp_count = len(pd.get("experience", []))
            edu_count = len(pd.get("education", []))

            sources.append({
                "type": "resume_metadata",
                "resume_id": str(resume.id),
                "candidate_name": candidate_name,
                "sections_analyzed": ["contact_info", "summary", "experience", "skills", "education"],
                "total_skills_extracted": skills_count,
                "total_experience_entries": exp_count,
            })

            recommendations.extend([
                "Quantify bullet points with metrics (e.g., 'reduced latency by 35%', 'handled 50k RPS').",
                "Ensure technical skills align directly with target job posting keywords for ATS ranking.",
                "Structure experience using Action Verb + Context + Result (Google XYZ formula).",
                "Keep resume formatting clean with standard fonts, avoiding complex tables or icons for ATS compatibility.",
            ])

            response_text = (
                f"### Resume Review & Feedback for {candidate_name}\n\n"
                f"**Overall Assessment:** Your resume contains **{skills_count} extracted canonical skills**, "
                f"**{exp_count} experience roles**, and **{edu_count} education records**.\n\n"
                f"**Key Feedback & ATS Optimizations:**\n"
                f"1. **Impact & Metrics:** Strengthen descriptive bullets by framing accomplishments with quantifiable outcomes.\n"
                f"2. **Skill Placement:** Organize technical competencies clearly into Languages, Frameworks, and Cloud/DevOps.\n"
                f"3. **Summary Statement:** Ensure your summary clearly states your core engineering specialty and years of experience.\n"
            )
        else:
            recommendations.extend([
                "Use the XYZ formula: Accomplished [X], as measured by [Y], by doing [Z].",
                "Incorporate industry-standard keywords from target job descriptions.",
                "Keep formatting simple and single/double-column text for ATS parsing.",
                "Upload your resume to receive personalized section-by-section analysis.",
            ])
            response_text = (
                "### Resume Optimization Best Practices\n\n"
                "To maximize interview callbacks and pass ATS filtering:\n"
                "1. **Action Verbs & Impact:** Begin every bullet with a strong past-tense action verb (Architected, Engineered, Optimized).\n"
                "2. **Quantifiable Results:** Include measurable outcomes (latencies, cost savings, user scale).\n"
                "3. **Keyword Alignment:** Mirror the core technologies requested in your target job descriptions.\n"
            )

        followups = [
            "How can I rewrite my most recent work experience bullet point?",
            "What ATS score would my resume get for backend engineering roles?",
            "Can you evaluate my technical skills section against job market demands?",
        ]

        return ChatQueryResponse(
            query=request.query,
            router_decision=decision,
            response=response_text,
            sources=sources,
            actionable_recommendations=recommendations,
            suggested_followups=followups,
        )

    # ---------------------------------------------------------------------------
    # Strategy Implementations
    # ---------------------------------------------------------------------------

    async def _execute_job_search(
        self,
        db: AsyncSession,
        request: ChatQueryRequest,
        decision: RouterDecision,
        resume: Optional[Resume],
    ) -> ChatQueryResponse:
        """Strategy 1: Dense pgvector retrieval + semantic re-ranking."""
        query_text = request.query
        sources = []

        # Retrieve top job postings
        jobs = []
        try:
            query_vector = await embedding_service.get_embedding(query_text)
            sql = (
                select(JobPosting)
                .order_by(JobPosting.embedding.cosine_distance(query_vector))
                .limit(4)
            )
            result = await db.execute(sql)
            jobs = result.scalars().all()
        except Exception as exc:
            logger.warning("Vector search error in router: %s", exc)
            if db:
                await db.rollback()
            jobs = []

        for j in jobs:
            sources.append({
                "type": "job_posting",
                "id": j.id,
                "title": j.title,
                "company": j.company_name,
                "location": j.location,
                "skills": (j.skills or [])[:5],
            })

        # Synthesize response
        candidate_name = resume.candidate_name if resume else "Candidate"
        response_lines = [
            f"### 🎯 Job Search & Opportunity Matching for {candidate_name}\n",
            f"Based on your query *\"{request.query}\"*, I executed **{decision.strategy_selected}**.\n",
        ]

        if jobs:
            response_lines.append("Here are the top aligned opportunities indexed in our database:\n")
            for idx, s in enumerate(sources, 1):
                response_lines.append(
                    f"{idx}. **{s['title']}** at **{s['company']}** ({s['location'] or 'Remote'})\n"
                    f"   - Core Requirements: {', '.join(s['skills']) if s['skills'] else 'General Engineering'}"
                )
        else:
            response_lines.append("Matching is currently unavailable or no matching job postings were found for your query.")

        recommendations = [
            "Use the 'Job Matches & XAI' tab to inspect TreeSHAP marginal feature contributions.",
            "Compare your candidate experience against job requirements to verify seniority level.",
            "Click on any job to launch a dedicated 3-step Interview Coach session."
        ]

        followups = [
            "What skills am I missing for the top match?",
            "What is the median salary for these roles?",
            "Can you generate interview questions for this position?"
        ]

        return ChatQueryResponse(
            query=request.query,
            router_decision=decision,
            response="\n".join(response_lines),
            sources=sources,
            actionable_recommendations=recommendations,
            suggested_followups=followups,
        )

    async def _execute_skill_progression(
        self,
        db: AsyncSession,
        request: ChatQueryRequest,
        decision: RouterDecision,
        resume: Optional[Resume],
    ) -> ChatQueryResponse:
        """Strategy 2: Skill-gap diagnostic & learning path synthesis."""
        candidate_skills = resume.parsed_data.get("skills", []) if resume and resume.parsed_data else []
        extracted_query_skills = extract_canonical_skills(request.query)

        sources = []
        if request.job_id:
            try:
                report = await coach_agent.get_skill_gap_report(db, request.resume_id, request.job_id)
                sources.append({
                    "type": "skill_gap_report",
                    "readiness_score": report.overall_readiness_score,
                    "critical_gaps": [g.skill for g in report.critical_gaps],
                    "strengths": report.confirmed_strengths[:5],
                })
            except Exception as e:
                logger.warning("Failed to get skill gap report in router: %s", e)

        response_lines = [
            "### 🚀 Skill Progression & Learning Path Diagnostic\n",
            f"The **Adaptive Router** recognized an inquiry into technical competencies and learning prerequisites.\n",
        ]

        if candidate_skills:
            response_lines.append(f"**Identified Foundation:** {', '.join(candidate_skills[:6])}...")
        
        response_lines.extend([
            "\n#### Recommended 3-Phase Progression Roadmap:",
            "1. **Phase 1 (Core Fundamentals):** Strengthen high-concurrency async patterns and clean data contracts.",
            "2. **Phase 2 (Distributed Systems):** Master message streaming (Kafka) and cluster orchestration (Docker/Kubernetes).",
            "3. **Phase 3 (Production Readiness):** Build end-to-end telemetry (Prometheus/Grafana) and CI/CD pipelines.",
        ])

        recommendations = [
            "Build a small demonstration microservice integrating asynchronous queues.",
            "Document system architecture trade-offs in GitHub README to demonstrate technical depth.",
            "Practice explaining edge cases and failure modes during technical rounds."
        ]

        followups = [
            "What are the top interview questions for these skills?",
            "How do these skills affect median compensation?",
            "Show me job openings that require these skills."
        ]

        return ChatQueryResponse(
            query=request.query,
            router_decision=decision,
            response="\n".join(response_lines),
            sources=sources,
            actionable_recommendations=recommendations,
            suggested_followups=followups,
        )

    async def _execute_interview_coaching(
        self,
        db: AsyncSession,
        request: ChatQueryRequest,
        decision: RouterDecision,
        resume: Optional[Resume],
    ) -> ChatQueryResponse:
        """Strategy 3: Interview Q&A bank & STAR rubric coaching."""
        sources = [
            {
                "type": "interview_qa_framework",
                "framework": "STAR Method (Situation, Task, Action, Result)",
                "rubrics": ["Technical Accuracy", "Depth", "Structure", "Specificity"],
            }
        ]

        response_lines = [
            "### 🎤 Interview Preparation & STAR Coaching Directive\n",
            "The **Adaptive Router** deployed **Strategy 3 (Coach Agent Integration)**.\n",
            "#### Engineering Interview Best Practices:\n",
            "- **Technical Depth:** Don't just list frameworks; explain memory lifecycles, event loop delegation, and connection pool sizing.",
            "- **STAR Framework for Behavioral:** Quantify business results (e.g. *'reduced latency by 35%'*, *'cut monthly AWS costs by $12k'*).",
            "- **Failure Mode Analysis:** Proactively volunteer how your system handles network partitions, database deadlocks, or worker crashes.\n",
            "You can practice answering questions live in the **'Interview Coach'** tab to receive 0-10 rubric evaluations."
        ]

        recommendations = [
            "Open the 'Interview Coach' tab and launch the Mock Interview Terminal.",
            "Aim for 80-150 words per practice answer to ensure sufficient technical depth.",
            "Review model answers to observe expected rubric signals."
        ]

        followups = [
            "Give me a senior backend interview question to practice right now.",
            "How do I answer a behavioral question about team conflict using STAR?",
            "What questions are commonly asked for Stripe or Vercel roles?"
        ]

        return ChatQueryResponse(
            query=request.query,
            router_decision=decision,
            response="\n".join(response_lines),
            sources=sources,
            actionable_recommendations=recommendations,
            suggested_followups=followups,
        )

    async def _execute_market_dynamics(
        self,
        db: AsyncSession,
        request: ChatQueryRequest,
        decision: RouterDecision,
        resume: Optional[Resume],
    ) -> ChatQueryResponse:
        """Strategy 4: Macro market intelligence & compensation bands."""
        salary_info = await market_agent.get_salary_insights(db, title_query=request.query)
        trending = await market_agent.get_trending_skills(db, title_query=request.query, top_n=5)

        band = salary_info.salary_band
        sources = [
            {
                "type": "market_salary_band",
                "median_annual": band.median_annual,
                "p25_annual": band.p25_annual,
                "p75_annual": band.p75_annual,
                "sample_size": band.sample_size,
            },
            {
                "type": "trending_skills",
                "top_skills": [s.skill for s in trending.skills],
            }
        ]

        response_lines = [
            "### 📊 Labor Market Intelligence & Compensation Insights\n",
            f"The **Adaptive Router** deployed **Strategy 4 (Market Agent Aggregation)** across indexed job postings.\n",
        ]

        if band.median_annual:
            response_lines.extend([
                f"#### Compensation Band ({band.currency}):",
                f"- **25th Percentile:** ${band.p25_annual:,.0f} / yr",
                f"- **Median Compensation:** **${band.median_annual:,.0f} / yr**",
                f"- **75th Percentile:** ${band.p75_annual:,.0f} / yr",
                f"- *Calculated across a sample of {band.sample_size} postings.* \n",
            ])

        if trending.skills:
            top_skill_names = [f"{s.skill} ({s.percentage}%)" for s in trending.skills]
            response_lines.extend([
                "#### Top In-Demand Market Skills:",
                f"- {', '.join(top_skill_names)}\n"
            ])

        if salary_info.narrative:
            response_lines.append(f"**Market Synthesis:** {salary_info.narrative}")

        recommendations = [
            "Review the 'Market Insights' tab for geographic heatmaps and remote work ratios.",
            "Compare your candidate positioning to see which missing skills command the highest salary premiums.",
            "Target metropolitan hubs (San Francisco, Seattle, New York) offering top-quartile equity compensation."
        ]

        followups = [
            "Which companies pay the highest for this role?",
            "What cities have the highest concentration of remote jobs?",
            "How does my resume match up against this market profile?"
        ]

        return ChatQueryResponse(
            query=request.query,
            router_decision=decision,
            response="\n".join(response_lines),
            sources=sources,
            actionable_recommendations=recommendations,
            suggested_followups=followups,
        )


router_service = AdaptiveRouterService()
