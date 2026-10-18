# Multi-Agent StateGraph Orchestrator Design (R4 Stage 1)

## Overview
This design document defines the LangGraph `StateGraph` architecture replacing the hand-written sequential orchestrator for the AI Career Copilot. It ensures that multi-agent execution is driven directly by the trained intent router, supports bounded retry on transient failures, tracks per-node execution latencies, preserves candidate ownership, and permits runtime backend toggling (`langgraph` vs `sequential`).

---

## 1. Graph State Schema (`GraphState`)

The state passed across nodes is a typed Python `TypedDict` compatible with LangGraph's functional node execution:

```python
from typing import Any, Dict, List, Optional, TypedDict

class GraphState(TypedDict, total=False):
    # Request Context
    query: str
    resume_id: Optional[str]
    job_id: Optional[str]
    raw_resume_text: Optional[str]
    target_role: Optional[str]
    target_location: Optional[str]
    
    # Router Decision
    intent: str                  # e.g. "JOB_SEARCH", "SKILL_GAP_ANALYSIS", "INTERVIEW_PREPARATION", "CAREER_ADVICE", "RESUME_FEEDBACK"
    confidence: float
    strategy_selected: str
    router_decision: Dict[str, Any]
    
    # Agent Outputs
    parsed_resume: Optional[Dict[str, Any]]
    matched_jobs: List[Dict[str, Any]]
    market_insights: Optional[Dict[str, Any]]
    coaching_plan: Optional[Dict[str, Any]]
    
    # Final Synthesized Response
    response: str
    sources: List[Dict[str, Any]]
    actionable_recommendations: List[str]
    suggested_followups: List[str]
    
    # Execution Tracking, Resilience & Observability
    completed_nodes: List[str]
    errors: List[Dict[str, Any]]       # AgentFailureRecord-compatible dicts
    retries: Dict[str, int]            # Per-node retry attempt counts
    node_timings_ms: Dict[str, float]  # Latency per node in milliseconds
    current_node: str
    next_node: Optional[str]
    retry_target: Optional[str]        # Target node when a retry edge is triggered
```

---

## 2. Graph Nodes

The StateGraph consists of 6 primary operational nodes:

1. **`route_node` (Entry Node)**:
   - Evaluates `query` using the trained intent router (`router_service.classify_intent`).
   - Populates `intent`, `confidence`, `strategy_selected`, and `router_decision`.
   - Records latency and appends `"route"` to `completed_nodes`.

2. **`parse_node`**:
   - If `resume_id` is supplied and valid in DB, loads and extracts `parsed_data`.
   - If `raw_resume_text` is supplied, executes `parser_agent.parse(raw_resume_text)`.
   - If neither is provided, passes through cleanly.
   - Populates `parsed_resume`.

3. **`match_node`**:
   - Executes dense vector retrieval and candidate qualification overlap matching against `JobPosting`.
   - Populates `matched_jobs`.

4. **`market_node`**:
   - Computes salary compensation percentiles (25th, median, 75th) and trending skill demand for the candidate's target role or matched job.
   - Populates `market_insights`.

5. **`coach_node`**:
   - Synthesizes skill gaps, readiness score, and interview question banks (technical, behavioral, gap-probing) tailored to the candidate and top matched role.
   - Populates `coaching_plan`.

6. **`synthesize_node` (Exit Node)**:
   - Aggregates multi-agent artifacts into a unified `response` (markdown), `sources`, `actionable_recommendations`, and `suggested_followups`.
   - Injects the `execution_trace` (containing `completed_nodes`, `node_timings_ms`, `retries`, and error records) into `sources` or response metadata.

---

## 3. Graph Routing & Conditional Edges

### 3.1 Intent-to-Agent Strategy Map (`STRATEGY_MAP`)
Matches the exact agent requirements documented in Stage 0:

- **`JOB_SEARCH`** (`JOB_SEARCH_AND_MATCH`):
  `route -> parse -> match -> synthesize -> END`
  *(If no resume context is provided, `parse` gracefully passes through to `match`)*.

- **`SKILL_GAP_ANALYSIS`** (`SKILL_PROGRESSION_AND_PATH`):
  `route -> parse -> match -> coach -> synthesize -> END`

- **`INTERVIEW_PREPARATION`** (`INTERVIEW_COACHING`):
  `route -> parse -> coach -> synthesize -> END`

- **`CAREER_ADVICE`** (`MACRO_MARKET_DYNAMICS`):
  `route -> parse -> market -> synthesize -> END`

- **`RESUME_FEEDBACK`**:
  `route -> parse -> coach -> synthesize -> END`

### 3.2 Conditional Router Function (`route_next_step`)
After `route_node`, the graph determines whether resume extraction is needed:
- If resume context exists (`resume_id` or `raw_resume_text`), routes to `parse`.
- If no resume context exists:
  - If `JOB_SEARCH` -> `match`
  - If `CAREER_ADVICE` -> `market`
  - If `INTERVIEW_PREPARATION` or `SKILL_GAP_ANALYSIS` or `RESUME_FEEDBACK` -> `coach`

After each agent node completes:
- `parse`: Routes to the first required domain agent for the intent:
  - `JOB_SEARCH` or `SKILL_GAP_ANALYSIS` -> `match`
  - `INTERVIEW_PREPARATION` or `RESUME_FEEDBACK` -> `coach`
  - `CAREER_ADVICE` -> `market`
- `match`:
  - If intent is `SKILL_GAP_ANALYSIS` -> routes to `coach`
  - Otherwise -> routes to `synthesize`
- `market`:
  - Routes to `synthesize`
- `coach`:
  - Routes to `synthesize`

---

## 4. Resilience: Bounded Retry and Partial Failure Policy

### 4.1 Transient vs Permanent Failures
- **Transient Failures**: Network timeouts, database pool blips, temporary service connection resets (`TimeoutError`, `httpx.TimeoutException`, `ConnectionError`).
- **Permanent Failures**: Schema validation errors, missing records, invalid format, `ValueError`, `KeyError`.

### 4.2 Bounded Retry Mechanism (`MAX_RETRIES = 1`)
- When a node encounters an exception:
  1. If the exception is transient and `retries[node] < 1`:
     - Increments `retries[node] += 1`.
     - Logs warning with retry count.
     - Routes back to the same node via a conditional retry edge (cyclic transition).
  2. If the retry fails or the exception is permanent:
     - Captures an error record:
       ```python
       {
           "agent_name": node,
           "step": node.upper(),
           "error_message": str(exc),
           "recovered": True,
           "timestamp": datetime.now(timezone.utc).isoformat()
       }
       ```
     - Populates resilient fallback artifacts so downstream nodes can proceed.
     - Advances to the next logical node in the DAG instead of terminating the pipeline.

---

## 5. Backend Toggle & Backward Compatibility
- Controlled by configuration setting `ORCHESTRATOR_BACKEND` (`"langgraph"` by default, with `"sequential"` fallback).
- Both backends consume `ChatQueryRequest` and return `ChatQueryResponse`, preserving identical API contracts and frontend compatibility.
- `MultiAgentOrchestrator` in `app/services/orchestrator.py` remains untouched as the reference sequential implementation.
