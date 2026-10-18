# Multi-Agent Orchestrator Baseline Audit (R4 Stage 0)

## Executive Summary
This document establishes the empirical baseline for the multi-agent orchestration subsystem of the AI Career Copilot project prior to the introduction of the LangGraph StateGraph (Phase R4).

## 1. Existing Orchestrator Architecture

### 1.1 `MultiAgentOrchestrator` (`app/services/orchestrator.py`)
The legacy orchestrator executes a linear, sequential pipeline using a typed Pydantic state model (`CareerWorkflowState`).

- **State Model**: `CareerWorkflowState` (`app/schemas/orchestrator.py`)
  - Tracks `workflow_id`, `status` (`WorkflowStatus`: PENDING, IN_PROGRESS, COMPLETED, PARTIAL_SUCCESS, FAILED), `current_step`, `completed_steps`.
  - Artifact slots: `parsed_resume` (`ParsedResume`), `matched_jobs` (`List[Dict]`), `market_insights` (`Optional[Dict]`), `coaching_plan` (`Optional[Dict]`), `executive_summary` (`Optional[str]`), `actionable_next_steps` (`List[str]`), `errors` (`List[AgentFailureRecord]`), `metadata` (`Dict[str, Any]`).
- **Control Flow**:
  - Node 1: `parser` (runs `parser_agent.parse` if `raw_resume_text` or loads from DB if `resume_id`).
  - Node 2: `matcher` (runs title-filtered query against `JobPosting` or deterministic mock fallback).
  - Node 3: `market` (extracts median/percentile compensation and trending skills via synthetic data or database).
  - Node 4: `coach` (constructs dummy `Resume` and `JobPosting` objects and calls `coach_agent.generate_skill_gap_report` and `coach_agent.generate_question_bank`).
  - Node 5: `synthesize` (deterministic summary formulation and actionable next steps).
- **Concurrency & Execution Model**:
  - Purely synchronous sequential execution (`await` calls in sequence within a single `async def execute_workflow`).
  - No concurrency (`asyncio.gather` is not used).
  - No conditional cycling or loops.
- **Partial Failure Handling**:
  - Each agent step is wrapped in `try...except Exception as exc:`.
  - Failures append an `AgentFailureRecord(agent_name=..., step=..., error_message=..., recovered=True, timestamp=...)` to `state.errors`.
  - If some steps succeed while others fail, overall status resolves to `WorkflowStatus.PARTIAL_SUCCESS`. If all enabled steps fail, resolves to `FAILED`.

### 1.2 Adaptive Router Chat Endpoint (`app/api/v1/endpoints/chat.py` & `app/services/router_service.py`)
The conversational endpoint `/api/v1/chat/query` currently bypasses `MultiAgentOrchestrator` entirely:
- `chat.py` validates `resume_id` ownership via `enforce_resume_ownership(res_obj, current_user)` and calls `router_service.route_and_execute(db=db, request=request)`.
- `router_service.route_and_execute` uses `classify_intent` (producing a `RouterDecision` with intent, confidence, strategy) and performs an `if/elif/else` dispatch to 5 strategy functions:
  1. `RESUME_FEEDBACK` -> `_execute_resume_feedback`
  2. `JOB_SEARCH_AND_MATCH` / `JOB_SEARCH` -> `_execute_job_search` (dense vector search over `JobPosting`)
  3. `SKILL_PROGRESSION_AND_PATH` / `SKILL_GAP_ANALYSIS` -> `_execute_skill_progression` (Coach agent integration if `job_id` provided, else structured roadmap)
  4. `INTERVIEW_COACHING` / `INTERVIEW_PREPARATION` -> `_execute_interview_coaching` (STAR framework and practice guidance)
  5. `MACRO_MARKET_DYNAMICS` / `CAREER_ADVICE` -> `_execute_market_dynamics` (queries `market_agent.get_salary_insights` and `market_agent.get_trending_skills`)
- **Limitation**: The router and the orchestrator are disjoint subsystems. Multi-step agent flows (e.g. parsing resume -> matching jobs -> analyzing skill gaps -> coaching synthesis) are not coordinated by a graph orchestrator when chatting.

## 2. Agent Invocation Matrix (By Intent)

| Intent / Strategy | Target Agents Run in Sequence | Artifacts Produced | Fallback Behavior |
| :--- | :--- | :--- | :--- |
| `JOB_SEARCH` (`JOB_SEARCH_AND_MATCH`) | `parser` (if resume context) -> `matcher` -> `synthesize` | `matched_jobs`, job sources | Title keyword fallback if vector search fails |
| `SKILL_GAP_ANALYSIS` (`SKILL_PROGRESSION_AND_PATH`) | `parser` -> `matcher` -> `coach` -> `synthesize` | `coaching_plan`, gap report sources | Heuristic skill extraction and generic progression roadmap |
| `INTERVIEW_PREPARATION` (`INTERVIEW_COACHING`) | `parser` -> `coach` -> `synthesize` | `coaching_plan` (question bank), STAR rubrics | Generic STAR rubric templates and interview tips |
| `CAREER_ADVICE` (`MACRO_MARKET_DYNAMICS`) | `parser` -> `market` -> `synthesize` | `market_insights`, salary bands, trending skills | Market database aggregation or role overview fallback |
| `RESUME_FEEDBACK` | `parser` -> `coach` (critique) -> `synthesize` | `parsed_resume`, ATS review suggestions | General XYZ bullet formula guidance |

## 3. Frontend Response Schema and Contract

The frontend (`frontend/src/components/chat/CopilotChatDrawer.jsx`) strictly consumes `ChatQueryResponse`:
```json
{
  "query": "string",
  "router_decision": {
    "intent": "JOB_SEARCH",
    "confidence": 0.95,
    "strategy_selected": "Strategy 1: Hybrid Vector Search & XGBoost Re-ranking",
    "reasoning": "Classified as job opportunity discovery...",
    "backend": "trained",
    "low_confidence": false,
    "fallback_used": false,
    "strategy": "Strategy 1: Hybrid Vector Search & XGBoost Re-ranking"
  },
  "response": "markdown string",
  "sources": [
    {
      "type": "job_posting",
      "id": "...",
      "title": "...",
      "company": "...",
      "location": "...",
      "skills": []
    }
  ],
  "actionable_recommendations": [
    "Step 1...",
    "Step 2..."
  ],
  "suggested_followups": [
    "Question 1?",
    "Question 2?"
  ]
}
```
Metadata such as `orchestrator_backend`, `execution_trace`, and per-node latencies can be safely attached to `sources` as an `execution_trace` record or embedded in responses without breaking frontend rendering.

## 4. Stage 0 Verification Baseline

- **Commit**: `c2584b9`
- **Backend Test Suite (venv)**: 369 passed in 541.45s
- **Backend Test Suite (venv-clean)**: 369 passed in 478.48s
- **Frontend Test Suite**: 19 passed in 182ms
- **Frontend Production Build**: Vite build completed successfully in 5.07s
- **Verified SHA-256 Hashes**:
  - `app/ranking/config.json`: `16C548207D3B10D8E56C30E61D2EA9E18701FA168A38C1CEBB6CB72044692331`
  - `data/evaluation/query_intent_benchmark_v1.json`: `8C8A49FABD58860E8EC82111C80C142A3F8765740B8709A48A919BAFED0106B4`
  - `data/evaluation/rag_coach_eval_v1.json`: `E6EA387146511A11139B42F53A3DD302E9C98EE57B211B2AB0C5299500B24598`
  - `data/router/test.jsonl`: `6340BB8A778BDC19A65A7E72EEF8F771AD7AE4AC7A0889912DC50BC679335AD4`
  - `artifacts/models/intent_router_v1.joblib`: `9FB2A9031E1910DC321FA69E14F3A67A711080019CF03235C15E4BCDC55785FD`

## 5. Cross-Backend Differences (Sequential vs. LangGraph)

The system supports toggling between `ORCHESTRATOR_BACKEND=sequential` (legacy `router_service.route_and_execute`) and `ORCHESTRATOR_BACKEND=langgraph` (`langgraph_orchestrator.execute`). The behavioral differences are intentional and detailed below:

1. **Observability & Trace Attributions**:
   - `langgraph`: Attaches an `orchestrator_trace` dictionary to the `sources` list containing `backend: "langgraph"`, `status` ("success" or "degraded: <agent>"), `completed_nodes`, `node_timings_ms`, `retries`, and `errors`.
   - `sequential`: Does not attach an execution trace or per-node latencies; `sources` contains only domain data items (e.g. `job_posting` objects).

2. **Multi-Agent State Accumulation**:
   - `langgraph`: Implements a `StateGraph` over typed `GraphState`. State is passed sequentially through nodes (`route` -> `parse` -> `match`/`market`/`coach` -> `synthesize`). Outputs from early nodes (such as parsed candidate skills from `parse` or retrieved opportunities from `match`) directly inform downstream prompts in `coach` or synthesis.
   - `sequential`: Dispatches immediately to an isolated single-strategy function (`_execute_job_search`, `_execute_skill_progression`, `_execute_interview_coaching`, `_execute_market_dynamics`, `_execute_resume_feedback`). Intermediate artifacts are not accumulated into a unified graph state.

3. **Fault Tolerance and Retry Semantics**:
   - `langgraph`: Implements bounded retry (`MAX_NODE_RETRIES = 1`) on transient network/timeout exceptions (`httpx.TimeoutException`, `httpx.ConnectError`, `asyncio.TimeoutError`, connection reset). Catches node failures non-fatally, records error diagnostics with target host/port attribution (`localhost:5432` Postgres, `localhost:11434` Ollama, etc.), and proceeds gracefully to downstream synthesis.
   - `sequential`: Relies on internal try-except blocks per strategy function with static mock fallbacks and no structured retry loops.

4. **Synthesis Formatting**:
   - `langgraph`: Formats synthesized responses with structured markdown headers, contextual skill highlights, actionable steps, and suggested follow-ups grounded in graph state.
   - `sequential`: Formats text within each separate strategy method with varying layout styles.

