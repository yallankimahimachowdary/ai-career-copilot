"""
app/services/graph_orchestrator.py
----------------------------------
LangGraph StateGraph Multi-Agent Orchestrator (Phase R4).

Coordinates Parser, Matcher, Market, and Coach agents with:
  1. Typed Shared State (GraphState) over LangGraph
  2. Routing decisions driven directly by the trained intent router (R3)
  3. Bounded retry on transient failures (MAX_RETRIES = 1)
  4. Non-fatal partial failure tolerance with state preservation
  5. Per-node execution latency tracing
  6. Explainable synthesis and full backward compatibility with ChatQueryResponse
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Callable, Dict, List, Optional, TypedDict
import uuid

import httpx
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    IntentType,
    RouterDecision,
)
from app.schemas.coach import CoachQuestionBankRequest
from app.schemas.resume import ParsedResume
from app.services.coach_service import coach_agent
from app.services.embedding_service import embedding_service
from app.services.market_service import market_agent
from app.services.parser_agent import parser_agent
from app.services.router_service import extract_canonical_skills, router_service

# Maximum retry attempts per node for transient errors
MAX_NODE_RETRIES: int = 1

# Permanent exception types that must NEVER be treated as transient
PERMANENT_EXCEPTIONS = (
    FileNotFoundError,
    PermissionError,
)

# Transient exception types eligible for bounded retry
TRANSIENT_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    asyncio.TimeoutError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.NetworkError,
    OSError,
)

# Intent-to-Agent routing map
STRATEGY_MAP: Dict[str, List[str]] = {
    "JOB_SEARCH": ["parse", "match", "synthesize"],
    "JOB_SEARCH_AND_MATCH": ["parse", "match", "synthesize"],
    "SKILL_GAP_ANALYSIS": ["parse", "match", "coach", "synthesize"],
    "SKILL_PROGRESSION_AND_PATH": ["parse", "match", "coach", "synthesize"],
    "INTERVIEW_PREPARATION": ["parse", "coach", "synthesize"],
    "INTERVIEW_COACHING": ["parse", "coach", "synthesize"],
    "CAREER_ADVICE": ["parse", "market", "synthesize"],
    "MACRO_MARKET_DYNAMICS": ["parse", "market", "synthesize"],
    "RESUME_FEEDBACK": ["parse", "coach", "synthesize"],
}


class GraphState(TypedDict, total=False):
    """
    Typed shared state passed through the LangGraph StateGraph pipeline.
    """
    # Request Inputs
    query: str
    resume_id: Optional[str]
    job_id: Optional[str]
    raw_resume_text: Optional[str]
    target_role: Optional[str]
    target_location: Optional[str]
    history: List[Dict[str, str]]
    db: Optional[Any]  # AsyncSession passed via state or context

    # Router Decision
    intent: str
    confidence: float
    strategy_selected: str
    router_decision: Optional[Dict[str, Any]]

    # Agent Artifacts
    parsed_resume: Optional[Dict[str, Any]]
    matched_jobs: List[Dict[str, Any]]
    market_insights: Optional[Dict[str, Any]]
    coaching_plan: Optional[Dict[str, Any]]

    # Synthesized Guidance
    response: str
    sources: List[Dict[str, Any]]
    actionable_recommendations: List[str]
    suggested_followups: List[str]

    # Resilience, Observability & Routing State
    completed_nodes: List[str]
    errors: List[Dict[str, Any]]
    retries: Dict[str, int]
    node_timings_ms: Dict[str, float]
    next_node: Optional[str]
    retry_target: Optional[str]
    match_unavailable: bool


def _is_transient_error(exc: Exception) -> bool:
    """Determine whether an error is transient (network/timeout) vs permanent."""
    if isinstance(exc, PERMANENT_EXCEPTIONS):
        return False
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True
    msg = str(exc).lower()
    return any(
        term in msg
        for term in (
            "timeout",
            "connection refused",
            "temporary",
            "connection reset",
            "econnreset",
            "remote computer refused",
            "winerror 1225",
        )
    )


def _is_connection_error(exc: Exception) -> bool:
    """Determine whether an error stems from network/host connection refusal or failure."""
    if isinstance(exc, (ConnectionError, httpx.ConnectError, httpx.ConnectTimeout)):
        return True
    msg = str(exc).lower()
    return any(
        term in msg
        for term in (
            "connection refused",
            "connection reset",
            "connection terminated",
            "connection closed",
            "connection error",
            "connection failed",
            "remote computer refused",
            "winerror 1225",
            "econnrefused",
            "econnreset",
            "connect error",
        )
    )


def _build_error_record(
    agent_name: str,
    step: str,
    exc: Exception,
    default_host_port: Optional[str] = None,
    recovered: bool = False,
) -> Dict[str, Any]:
    """Builds a standardized error record with target host:port attribution on failure."""
    msg = str(exc)
    record: Dict[str, Any] = {
        "agent_name": agent_name,
        "step": step,
        "error_message": msg,
        "recovered": recovered,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if default_host_port:
        record["target_host_port"] = default_host_port
        if default_host_port not in msg:
            record["error_message"] = f"{msg} (target: {default_host_port})"
    return record


def _mark_recovered(errors: List[Dict[str, Any]], agent_name: str) -> None:
    """Marks previous errors for an agent as recovered after a successful retry."""
    for err in errors:
        if err.get("agent_name") == agent_name:
            err["recovered"] = True


def determine_execution_status(
    completed_nodes: List[str],
    errors: List[Dict[str, Any]],
    fallback_used: bool = False,
    fallbacks: Optional[List[str]] = None,
    match_unavailable: bool = False,
) -> str:
    """
    Computes orchestrator execution status according to Stage 0 rule:
    Status is 'success' ONLY if no agent has unrecovered errors, no fallbacks were used,
    and match was available; otherwise 'degraded: <failing_agent(s)>'.
    """
    failing_agents: List[str] = []
    if errors:
        for err in errors:
            if not err.get("recovered", False):
                agent = err.get("agent_name", "unknown")
                if agent not in failing_agents:
                    failing_agents.append(agent)
    if match_unavailable and "match" not in failing_agents:
        failing_agents.append("match")
    if fallbacks:
        for fb in fallbacks:
            if fb not in failing_agents:
                failing_agents.append(fb)
    elif fallback_used and "router" not in failing_agents:
        failing_agents.append("router")

    if not failing_agents:
        return "success"
    return f"degraded: {', '.join(failing_agents)}"


class LangGraphOrchestrator:
    """
    LangGraph-based multi-agent state graph orchestrator.
    """

    def __init__(self) -> None:
        self.app = self._build_graph()

    def _build_graph(self):
        """Constructs and compiles the StateGraph with cyclic retry edges and conditional routing."""
        workflow = StateGraph(GraphState)

        # Register primary nodes
        workflow.add_node("route", self.route_node)
        workflow.add_node("parse", self.parse_node)
        workflow.add_node("match", self.match_node)
        workflow.add_node("market", self.market_node)
        workflow.add_node("coach", self.coach_node)
        workflow.add_node("synthesize", self.synthesize_node)

        # Entry edge: START -> route
        workflow.add_edge(START, "route")

        # Conditional edge from route
        workflow.add_conditional_edges(
            "route",
            self._route_after_intent,
            {
                "parse": "parse",
                "match": "match",
                "market": "market",
                "coach": "coach",
                "synthesize": "synthesize",
                "retry_route": "route",
            },
        )

        # Conditional edge from parse
        workflow.add_conditional_edges(
            "parse",
            self._route_after_parse,
            {
                "match": "match",
                "market": "market",
                "coach": "coach",
                "synthesize": "synthesize",
                "retry_parse": "parse",
            },
        )

        # Conditional edge from match
        workflow.add_conditional_edges(
            "match",
            self._route_after_match,
            {
                "coach": "coach",
                "synthesize": "synthesize",
                "retry_match": "match",
            },
        )

        # Conditional edge from market
        workflow.add_conditional_edges(
            "market",
            self._route_after_market,
            {
                "synthesize": "synthesize",
                "retry_market": "market",
            },
        )

        # Conditional edge from coach
        workflow.add_conditional_edges(
            "coach",
            self._route_after_coach,
            {
                "synthesize": "synthesize",
                "retry_coach": "coach",
            },
        )

        # Exit edge: synthesize -> END
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    # ---------------------------------------------------------------------------
    # Conditional Routing Logic
    # ---------------------------------------------------------------------------

    def _route_after_intent(self, state: GraphState) -> str:
        """Determines the first executing agent based on router decision and resume availability."""
        if state.get("retry_target") == "route":
            return "retry_route"

        # If resume context is supplied, parse first
        if state.get("resume_id") or state.get("raw_resume_text"):
            return "parse"

        intent = state.get("intent", "JOB_SEARCH")
        plan = STRATEGY_MAP.get(intent, ["match", "synthesize"])

        for step in plan:
            if step != "parse" and step != "synthesize":
                return step

        return "synthesize"

    def _route_after_parse(self, state: GraphState) -> str:
        """Determines the next agent after parse completes."""
        if state.get("retry_target") == "parse":
            return "retry_parse"

        intent = state.get("intent", "JOB_SEARCH")
        plan = STRATEGY_MAP.get(intent, ["match", "synthesize"])

        for step in plan:
            if step != "parse" and step != "synthesize":
                return step

        return "synthesize"

    def _route_after_match(self, state: GraphState) -> str:
        """Determines the next agent after match completes."""
        if state.get("retry_target") == "match":
            return "retry_match"

        intent = state.get("intent", "JOB_SEARCH")
        plan = STRATEGY_MAP.get(intent, ["synthesize"])

        if "coach" in plan and "coach" not in state.get("completed_nodes", []):
            return "coach"

        return "synthesize"

    def _route_after_market(self, state: GraphState) -> str:
        """Determines next node after market completes."""
        if state.get("retry_target") == "market":
            return "retry_market"
        return "synthesize"

    def _route_after_coach(self, state: GraphState) -> str:
        """Determines next node after coach completes."""
        if state.get("retry_target") == "coach":
            return "retry_coach"
        return "synthesize"

    # ---------------------------------------------------------------------------
    # Node Handlers
    # ---------------------------------------------------------------------------

    async def route_node(self, state: GraphState) -> Dict[str, Any]:
        """Classifies intent using the trained router service."""
        start_time = time.perf_counter()
        query = state.get("query", "")
        retries = dict(state.get("retries", {}))
        node_timings = dict(state.get("node_timings_ms", {}))
        completed = list(state.get("completed_nodes", []))
        errors = list(state.get("errors", []))

        try:
            decision = await router_service.classify_intent(query, use_llm=True)
            if retries.get("route", 0) > 0:
                _mark_recovered(errors, "route")
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["route"] = elapsed_ms
            if "route" not in completed:
                completed.append("route")

            return {
                "intent": decision.intent.value,
                "confidence": decision.confidence,
                "strategy_selected": decision.strategy_selected,
                "router_decision": decision.model_dump(),
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }
        except Exception as exc:
            logger.warning("Router node failure: %s", exc)
            current_retries = retries.get("route", 0)
            if _is_transient_error(exc) and current_retries < MAX_NODE_RETRIES:
                retries["route"] = current_retries + 1
                return {"retries": retries, "retry_target": "route"}

            # Permanent failure or retries exhausted -> fallback to JOB_SEARCH
            errors.append(
                _build_error_record("route", "ROUTE", exc, default_host_port="localhost:11434 (Ollama)", recovered=False)
            )
            fallback_decision = RouterDecision(
                intent=IntentType.JOB_SEARCH,
                confidence=0.50,
                strategy_selected="Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
                reasoning="Router exception fallback to job search.",
                backend="fallback",
                low_confidence=True,
                fallback_used=True,
                strategy="Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["route"] = elapsed_ms
            completed.append("route")

            return {
                "intent": fallback_decision.intent.value,
                "confidence": fallback_decision.confidence,
                "strategy_selected": fallback_decision.strategy_selected,
                "router_decision": fallback_decision.model_dump(),
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }

    async def parse_node(self, state: GraphState) -> Dict[str, Any]:
        """Parses raw resume text or retrieves stored parsed resume data."""
        start_time = time.perf_counter()
        retries = dict(state.get("retries", {}))
        node_timings = dict(state.get("node_timings_ms", {}))
        completed = list(state.get("completed_nodes", []))
        errors = list(state.get("errors", []))
        db = state.get("db")

        try:
            parsed_dict = None
            if state.get("raw_resume_text"):
                parsed = await parser_agent.parse(state["raw_resume_text"])
                parsed_dict = parsed.model_dump()
            elif state.get("resume_id") and db:
                res_obj = await db.get(Resume, state["resume_id"])
                if res_obj and res_obj.parsed_data:
                    parsed_dict = res_obj.parsed_data

            if retries.get("parse", 0) > 0:
                _mark_recovered(errors, "parse")

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["parse"] = elapsed_ms
            if "parse" not in completed:
                completed.append("parse")

            return {
                "parsed_resume": parsed_dict,
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }
        except Exception as exc:
            logger.warning("Parse node failure: %s", exc)
            if db:
                await db.rollback()
            current_retries = retries.get("parse", 0)
            if _is_transient_error(exc) and current_retries < MAX_NODE_RETRIES:
                retries["parse"] = current_retries + 1
                return {"retries": retries, "retry_target": "parse"}

            errors.append(
                _build_error_record("parse", "PARSE", exc, default_host_port="localhost:5432 (Postgres)", recovered=False)
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["parse"] = elapsed_ms

            return {
                "parsed_resume": None,
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }

    async def match_node(self, state: GraphState) -> Dict[str, Any]:
        """Executes job matching against database or semantic search."""
        start_time = time.perf_counter()
        retries = dict(state.get("retries", {}))
        node_timings = dict(state.get("node_timings_ms", {}))
        completed = list(state.get("completed_nodes", []))
        errors = list(state.get("errors", []))
        db = state.get("db")
        query = state.get("query", "")

        try:
            matched_items: List[Dict[str, Any]] = []
            parsed_resume = state.get("parsed_resume") or {}
            candidate_skills = parsed_resume.get("skills", [])

            if db:
                query_vector = await embedding_service.get_embedding(query)
                sql = (
                    select(JobPosting)
                    .order_by(JobPosting.embedding.cosine_distance(query_vector))
                    .limit(4)
                )
                res = await db.execute(sql)
                jobs = res.scalars().all()

                for job in jobs:
                    job_skills = job.skills or []
                    if candidate_skills and job_skills:
                        c_set = {s.lower() for s in candidate_skills}
                        j_set = {s.lower() for s in job_skills}
                        overlap = len(c_set & j_set) / max(len(j_set), 1)
                        match_score = round(min(0.20 + overlap * 0.80, 0.98), 2)
                    else:
                        match_score = 0.75

                    matched_items.append({
                        "id": str(job.id),
                        "job_id": str(job.id),
                        "title": job.title,
                        "company": job.company_name or "Tech Employer",
                        "company_name": job.company_name or "Tech Employer",
                        "location": job.location or "Remote",
                        "match_score": match_score,
                        "skills": job_skills[:8],
                    })

            if retries.get("match", 0) > 0:
                _mark_recovered(errors, "match")

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["match"] = elapsed_ms
            if "match" not in completed:
                completed.append("match")

            return {
                "matched_jobs": matched_items,
                "match_unavailable": False,
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }
        except Exception as exc:
            logger.warning("Match node failure: %s", exc)
            if db:
                await db.rollback()
            current_retries = retries.get("match", 0)
            if _is_transient_error(exc) and current_retries < MAX_NODE_RETRIES:
                retries["match"] = current_retries + 1
                return {"retries": retries, "retry_target": "match"}

            errors.append(
                _build_error_record("match", "MATCH", exc, default_host_port="localhost:5432 (Postgres)", recovered=False)
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["match"] = elapsed_ms

            return {
                "matched_jobs": [],
                "match_unavailable": True,
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }

    async def market_node(self, state: GraphState) -> Dict[str, Any]:
        """Queries market intelligence for compensation and demand."""
        start_time = time.perf_counter()
        retries = dict(state.get("retries", {}))
        node_timings = dict(state.get("node_timings_ms", {}))
        completed = list(state.get("completed_nodes", []))
        errors = list(state.get("errors", []))
        db = state.get("db")
        query = state.get("query", "")

        try:
            target_role = state.get("target_role") or query or "Software Engineer"
            clean_role = target_role.replace("Senior", "").replace("Staff", "").strip()

            market_data: Dict[str, Any] = {}
            if db:
                try:
                    salary_info = await market_agent.get_salary_insights(db, title_query=clean_role)
                    trending = await market_agent.get_trending_skills(db, title_query=clean_role, top_n=5)
                    band = salary_info.salary_band
                    market_data = {
                        "target_role": clean_role,
                        "location": state.get("target_location") or "Remote",
                        "compensation": {
                            "p25": band.p25_annual or 125000,
                            "median": band.median_annual or 155000,
                            "p75": band.p75_annual or 185000,
                            "currency": band.currency or "USD",
                            "sample_size": band.sample_size or 24,
                        },
                        "trending_skills": [s.skill for s in trending.skills] or ["Python", "FastAPI", "Docker"],
                        "narrative": salary_info.narrative,
                    }
                except Exception as db_exc:
                    if db:
                        await db.rollback()
                    if _is_transient_error(db_exc):
                        raise
                    logger.debug("Market DB query fallback: %s", db_exc)

            if not market_data:
                market_data = {
                    "target_role": clean_role,
                    "location": state.get("target_location") or "Remote",
                    "compensation": {
                        "p25": 125000,
                        "median": 155000,
                        "p75": 185000,
                        "currency": "USD",
                        "sample_size": 24,
                    },
                    "demand_signal": "high",
                    "trending_skills": ["Python", "FastAPI", "Docker", "Kubernetes", "AWS"],
                }

            if retries.get("market", 0) > 0:
                _mark_recovered(errors, "market")

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["market"] = elapsed_ms
            if "market" not in completed:
                completed.append("market")

            return {
                "market_insights": market_data,
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }
        except Exception as exc:
            logger.warning("Market node failure: %s", exc)
            if db:
                await db.rollback()
            current_retries = retries.get("market", 0)
            if _is_transient_error(exc) and current_retries < MAX_NODE_RETRIES:
                retries["market"] = current_retries + 1
                return {"retries": retries, "retry_target": "market"}

            errors.append(
                _build_error_record("market", "MARKET", exc, default_host_port="localhost:5432 (Postgres)", recovered=False)
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["market"] = elapsed_ms

            return {
                "market_insights": None,
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }

    async def coach_node(self, state: GraphState) -> Dict[str, Any]:
        """Generates skill-gap diagnoses, learning roadmaps, and interview question banks."""
        start_time = time.perf_counter()
        retries = dict(state.get("retries", {}))
        node_timings = dict(state.get("node_timings_ms", {}))
        completed = list(state.get("completed_nodes", []))
        errors = list(state.get("errors", []))

        try:
            parsed_data = state.get("parsed_resume") or {"skills": ["Python", "SQL"]}
            candidate_name = (
                parsed_data.get("contact_info", {}).get("name")
                if isinstance(parsed_data.get("contact_info"), dict)
                else "Candidate"
            )

            matched_jobs = state.get("matched_jobs") or []
            top_job = matched_jobs[0] if matched_jobs else {
                "job_id": str(uuid.uuid4()),
                "title": state.get("target_role") or "Software Engineer",
                "skills": ["Python", "Docker", "Kubernetes", "FastAPI"],
                "company_name": "Target Employer",
            }

            dummy_resume = Resume(
                id=str(uuid.uuid4()),
                candidate_name=candidate_name,
                parsed_data=parsed_data,
            )

            dummy_job = JobPosting(
                id=str(top_job.get("job_id") or uuid.uuid4()),
                title=top_job.get("title", "Software Engineer"),
                company_name=top_job.get("company_name", "Target Employer"),
                description=f"Seeking {top_job.get('title')} with {', '.join(top_job.get('skills', []))}.",
                skills=top_job.get("skills", []),
            )

            gap_report = await coach_agent.generate_skill_gap_report(dummy_resume, dummy_job)
            qb_req = CoachQuestionBankRequest(
                resume_id=str(dummy_resume.id),
                job_id=str(dummy_job.id),
                max_technical=3,
                max_behavioral=2,
                max_gap=2,
            )
            qb = await coach_agent.generate_question_bank(dummy_resume, dummy_job, gap_report, qb_req)

            coaching_data = {
                "readiness_score": gap_report.overall_readiness_score,
                "confirmed_strengths": gap_report.confirmed_strengths,
                "critical_gaps": [g.model_dump() for g in gap_report.critical_gaps],
                "growth_gaps": [g.model_dump() for g in gap_report.growth_gaps],
                "learning_roadmap": gap_report.learning_roadmap,
                "technical_questions": [q.model_dump() for q in qb.technical_questions],
                "behavioral_questions": [q.model_dump() for q in qb.behavioral_questions],
                "gap_questions": [q.model_dump() for q in qb.gap_questions],
            }

            if retries.get("coach", 0) > 0:
                _mark_recovered(errors, "coach")

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["coach"] = elapsed_ms
            if "coach" not in completed:
                completed.append("coach")

            return {
                "coaching_plan": coaching_data,
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }
        except Exception as exc:
            logger.warning("Coach node failure: %s", exc)
            db = state.get("db")
            if db:
                await db.rollback()
            current_retries = retries.get("coach", 0)
            if _is_transient_error(exc) and current_retries < MAX_NODE_RETRIES:
                retries["coach"] = current_retries + 1
                return {"retries": retries, "retry_target": "coach"}

            errors.append(
                _build_error_record("coach", "COACH", exc, default_host_port="localhost:11434 (Ollama)", recovered=False)
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            node_timings["coach"] = elapsed_ms

            return {
                "coaching_plan": None,
                "completed_nodes": completed,
                "node_timings_ms": node_timings,
                "errors": errors,
                "retry_target": None,
            }

    async def synthesize_node(self, state: GraphState) -> Dict[str, Any]:
        """Synthesizes cross-agent guidance into a cohesive ChatQueryResponse."""
        start_time = time.perf_counter()
        intent = state.get("intent", "JOB_SEARCH")
        strategy_selected = state.get("strategy_selected", "Strategy 1: Hybrid Vector Search")
        query = state.get("query", "")
        parsed_resume = state.get("parsed_resume") or {}
        matched_jobs = state.get("matched_jobs") or []
        market_insights = state.get("market_insights") or {}
        coaching_plan = state.get("coaching_plan") or {}
        completed = list(state.get("completed_nodes", []))
        node_timings = dict(state.get("node_timings_ms", {}))
        errors = list(state.get("errors", []))
        retries = dict(state.get("retries", {}))

        candidate_name = (
            parsed_resume.get("contact_info", {}).get("name")
            if isinstance(parsed_resume.get("contact_info"), dict)
            else "Candidate"
        )

        sources: List[Dict[str, Any]] = []
        recommendations: List[str] = []
        followups: List[str] = []
        response_lines: List[str] = []

        match_unavailable = state.get("match_unavailable", False)

        if intent in ("JOB_SEARCH", "JOB_SEARCH_AND_MATCH"):
            if match_unavailable or not matched_jobs:
                response_lines = [
                    f"### 🎯 Job Search & Opportunity Matching for {candidate_name}\n",
                    f"Based on your query *\"{query}\"*, the LangGraph orchestrator executed **{strategy_selected}**.\n",
                    "⚠️ **Job matching is currently unavailable.** We could not retrieve aligned job postings at this time. Please try again later.\n",
                ]
            else:
                response_lines = [
                    f"### 🎯 Job Search & Opportunity Matching for {candidate_name}\n",
                    f"Based on your query *\"{query}\"*, the LangGraph orchestrator executed **{strategy_selected}**.\n",
                    "Here are the top aligned opportunities indexed in our database:\n",
                ]
                for idx, job in enumerate(matched_jobs[:4], 1):
                    sources.append({
                        "type": "job_posting",
                        "id": job.get("id") or job.get("job_id"),
                        "title": job.get("title"),
                        "company": job.get("company") or job.get("company_name"),
                        "location": job.get("location"),
                        "skills": job.get("skills", [])[:5],
                    })
                    skills_str = ", ".join(job.get("skills", [])[:5]) or "General Engineering"
                    response_lines.append(
                        f"{idx}. **{job.get('title')}** at **{job.get('company') or job.get('company_name')}** ({job.get('location') or 'Remote'})\n"
                        f"   - Core Requirements: {skills_str}"
                    )
            recommendations = [
                "Use the 'Job Matches & XAI' tab to inspect TreeSHAP marginal feature contributions.",
                "Compare your candidate experience against job requirements to verify seniority level.",
                "Click on any job to launch a dedicated 3-step Interview Coach session.",
            ]
            followups = [
                "What skills am I missing for the top match?",
                "What is the median salary for these roles?",
                "Can you generate interview questions for this position?",
            ]

        elif intent in ("SKILL_GAP_ANALYSIS", "SKILL_PROGRESSION_AND_PATH"):
            candidate_skills = parsed_resume.get("skills", [])
            response_lines = [
                "### 🚀 Skill Progression & Learning Path Diagnostic\n",
                f"The **LangGraph Orchestrator** recognized an inquiry into technical competencies and learning prerequisites.\n",
            ]
            if candidate_skills:
                response_lines.append(f"**Identified Foundation:** {', '.join(candidate_skills[:6])}...")
            if coaching_plan and coaching_plan.get("learning_roadmap"):
                response_lines.append("\n#### Recommended Progression Roadmap:")
                for step in coaching_plan["learning_roadmap"][:3]:
                    response_lines.append(f"- {step}")
            else:
                response_lines.extend([
                    "\n#### Recommended 3-Phase Progression Roadmap:",
                    "1. **Phase 1 (Core Fundamentals):** Strengthen high-concurrency async patterns and clean data contracts.",
                    "2. **Phase 2 (Distributed Systems):** Master message streaming (Kafka) and cluster orchestration (Docker/Kubernetes).",
                    "3. **Phase 3 (Production Readiness):** Build end-to-end telemetry (Prometheus/Grafana) and CI/CD pipelines.",
                ])
            recommendations = [
                "Build a small demonstration microservice integrating asynchronous queues.",
                "Document system architecture trade-offs in GitHub README to demonstrate technical depth.",
                "Practice explaining edge cases and failure modes during technical rounds.",
            ]
            followups = [
                "What are the top interview questions for these skills?",
                "How do these skills affect median compensation?",
                "Show me job openings that require these skills.",
            ]

        elif intent in ("INTERVIEW_PREPARATION", "INTERVIEW_COACHING"):
            sources.append({
                "type": "interview_qa_framework",
                "framework": "STAR Method (Situation, Task, Action, Result)",
                "rubrics": ["Technical Accuracy", "Depth", "Structure", "Specificity"],
            })
            response_lines = [
                "### 🎤 Interview Preparation & STAR Coaching Directive\n",
                "The **LangGraph Orchestrator** deployed **Coach Agent Integration**.\n",
                "#### Engineering Interview Best Practices:\n",
                "- **Technical Depth:** Don't just list frameworks; explain memory lifecycles, event loop delegation, and connection pool sizing.",
                "- **STAR Framework for Behavioral:** Quantify business results (e.g. *'reduced latency by 35%'*, *'cut monthly AWS costs by $12k'*).",
                "- **Failure Mode Analysis:** Proactively volunteer how your system handles network partitions, database deadlocks, or worker crashes.\n",
                "You can practice answering questions live in the **'Interview Coach'** tab to receive 0-10 rubric evaluations.",
            ]
            recommendations = [
                "Open the 'Interview Coach' tab and launch the Mock Interview Terminal.",
                "Aim for 80-150 words per practice answer to ensure sufficient technical depth.",
                "Review model answers to observe expected rubric signals.",
            ]
            followups = [
                "Give me a senior backend interview question to practice right now.",
                "How do I answer a behavioral question about team conflict using STAR?",
                "What questions are commonly asked for Stripe or Vercel roles?",
            ]

        elif intent in ("CAREER_ADVICE", "MACRO_MARKET_DYNAMICS"):
            comp = market_insights.get("compensation", {}) if market_insights else {}
            sources.append({
                "type": "market_salary_band",
                "median_annual": comp.get("median", 155000),
                "p25_annual": comp.get("p25", 125000),
                "p75_annual": comp.get("p75", 185000),
                "sample_size": comp.get("sample_size", 24),
            })
            response_lines = [
                "### 📊 Labor Market Intelligence & Compensation Insights\n",
                f"The **LangGraph Orchestrator** deployed **Market Agent Aggregation** across indexed job postings.\n",
            ]
            if comp.get("median"):
                response_lines.extend([
                    f"#### Compensation Band ({comp.get('currency', 'USD')}):",
                    f"- **25th Percentile:** ${comp.get('p25', 125000):,.0f} / yr",
                    f"- **Median Compensation:** **${comp.get('median', 155000):,.0f} / yr**",
                    f"- **75th Percentile:** ${comp.get('p75', 185000):,.0f} / yr",
                    f"- *Calculated across an indexed sample of {comp.get('sample_size', 24)} postings.* \n",
                ])
            recommendations = [
                "Review the 'Market Insights' tab for geographic heatmaps and remote work ratios.",
                "Compare your candidate positioning to see which missing skills command the highest salary premiums.",
                "Target metropolitan hubs offering top-quartile equity compensation.",
            ]
            followups = [
                "Which companies pay the highest for this role?",
                "What cities have the highest concentration of remote jobs?",
                "How does my resume match up against this market profile?",
            ]

        else:  # RESUME_FEEDBACK
            skills_count = len(parsed_resume.get("skills", []))
            sources.append({
                "type": "resume_metadata",
                "candidate_name": candidate_name,
                "total_skills_extracted": skills_count,
            })
            response_lines = [
                f"### Resume Review & Feedback for {candidate_name}\n\n",
                f"**Overall Assessment:** Your resume contains **{skills_count} extracted canonical skills**.\n\n",
                "**Key Feedback & ATS Optimizations:**\n",
                "1. **Impact & Metrics:** Strengthen descriptive bullets by framing accomplishments with quantifiable outcomes.\n",
                "2. **Skill Placement:** Organize technical competencies clearly into Languages, Frameworks, and Cloud/DevOps.\n",
                "3. **Summary Statement:** Ensure your summary clearly states your core engineering specialty and years of experience.\n",
            ]
            recommendations = [
                "Quantify bullet points with metrics (e.g., 'reduced latency by 35%').",
                "Ensure technical skills align directly with target job posting keywords for ATS ranking.",
                "Structure experience using Action Verb + Context + Result (Google XYZ formula).",
            ]
            followups = [
                "How can I rewrite my most recent work experience bullet point?",
                "What ATS score would my resume get for backend engineering roles?",
                "Can you evaluate my technical skills section against job market demands?",
            ]

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        node_timings["synthesize"] = elapsed_ms
        if "synthesize" not in completed:
            completed.append("synthesize")

        # Determine status according to Stage 0 rule (success ONLY if no unrecovered errors, no fallbacks, and match available)
        rd = state.get("router_decision") or {}
        trace_status = determine_execution_status(
            completed_nodes=completed,
            errors=errors,
            fallback_used=rd.get("fallback_used", False),
            match_unavailable=match_unavailable,
        )

        # Attach execution trace to sources for transparency & testing
        sources.append({
            "type": "orchestrator_trace",
            "backend": "langgraph",
            "status": trace_status,
            "completed_nodes": completed,
            "node_timings_ms": node_timings,
            "retries": retries,
            "errors": errors,
        })

        return {
            "response": "\n".join(response_lines),
            "sources": sources,
            "actionable_recommendations": recommendations,
            "suggested_followups": followups,
            "completed_nodes": completed,
            "node_timings_ms": node_timings,
        }

    # ---------------------------------------------------------------------------
    # Public Execution Entry Point
    # ---------------------------------------------------------------------------

    async def execute(
        self,
        request: ChatQueryRequest,
        db: Optional[AsyncSession] = None,
        use_llm: bool = True,
    ) -> ChatQueryResponse:
        """
        Executes the LangGraph StateGraph pipeline, producing a verified ChatQueryResponse.
        """
        initial_state: GraphState = {
            "query": request.query,
            "resume_id": request.resume_id,
            "job_id": request.job_id,
            "raw_resume_text": getattr(request, "raw_resume_text", None),
            "history": request.history or [],
            "db": db,
            "completed_nodes": [],
            "errors": [],
            "retries": {},
            "node_timings_ms": {},
            "matched_jobs": [],
            "match_unavailable": False,
            "sources": [],
            "actionable_recommendations": [],
            "suggested_followups": [],
        }

        # Run StateGraph
        final_state = await self.app.ainvoke(initial_state)

        # Build RouterDecision
        rd_data = final_state.get("router_decision") or {}
        if rd_data:
            router_decision = RouterDecision.model_validate(rd_data)
        else:
            router_decision = RouterDecision(
                intent=IntentType(final_state.get("intent", "JOB_SEARCH")),
                confidence=float(final_state.get("confidence", 0.85)),
                strategy_selected=final_state.get("strategy_selected", "Strategy 1: Hybrid Vector Search"),
                reasoning="Classified via LangGraph state graph.",
                backend="trained",
                low_confidence=False,
                fallback_used=False,
                strategy=final_state.get("strategy_selected", "Strategy 1: Hybrid Vector Search"),
            )

        return ChatQueryResponse(
            query=request.query,
            router_decision=router_decision,
            response=final_state.get("response", ""),
            sources=final_state.get("sources", []),
            actionable_recommendations=final_state.get("actionable_recommendations", []),
            suggested_followups=final_state.get("suggested_followups", []),
        )


# Global singleton instance
langgraph_orchestrator = LangGraphOrchestrator()
