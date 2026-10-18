# Frontend Integration & Architecture Audit

**Project:** AI Career Copilot  
**Author:** Remediation R7  
**Status:** Canonical Reference  
**Last Updated:** October 2026  

---

## 1. Complete API Endpoint Mapping

The following matrix documents every active FastAPI backend route (`/api/v1/*`), its corresponding frontend client caller, source location, outgoing payload schema, and expected response schema.

| Backend Endpoint | Method | Frontend Client Caller | Source File & Line | Request Payload / Params | Expected Response Schema |
|:---|:---|:---|:---|:---|:---|
| `/api/v1/health` | `GET` | `apiClient.get("/health")` | [`frontend/src/App.jsx:30`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/App.jsx#L30) | None | `{ "status": "healthy" \| "ok" }` |
| `/api/v1/auth/register` | `POST` | `authApi.register(data)` | [`frontend/src/api/authApi.js:4`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/authApi.js#L4) | `{ email, password, full_name? }` | `UserResponse` (`id`, `email`, `full_name`, `created_at`) |
| `/api/v1/auth/login` | `POST` | `authApi.login(data)` | [`frontend/src/api/authApi.js:9`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/authApi.js#L9) | `{ email, password }` | `Token` (`access_token`, `token_type`, `user`) |
| `/api/v1/auth/me` | `GET` | `authApi.getMe()` | [`frontend/src/api/authApi.js:14`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/authApi.js#L14) | None (Bearer token in header) | `UserResponse` (`id`, `email`, `full_name`, `is_active`) |
| `/api/v1/resumes/upload` | `POST` | `resumeApi.uploadResume(formData)` | [`frontend/src/api/resumeApi.js:4`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/resumeApi.js#L4) | `FormData` (`file: File`) | `ResumeResponse` (`id`, `filename`, `parsed_data`, `created_at`) |
| `/api/v1/resumes/` | `GET` | `resumeApi.getResumes()` | [`frontend/src/api/resumeApi.js:13`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/resumeApi.js#L13) | None | `List[ResumeResponse]` |
| `/api/v1/resumes/{resume_id}` | `GET` | `resumeApi.getResume(id)` | [`frontend/src/api/resumeApi.js:18`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/resumeApi.js#L18) | URL path `resume_id` | `ResumeResponse` |
| `/api/v1/resumes/{resume_id}` | `DELETE` | `resumeApi.deleteResume(id)` | [`frontend/src/api/resumeApi.js:23`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/resumeApi.js#L23) | URL path `resume_id` | `{ "message": "Resume deleted" }` |
| `/api/v1/matcher/match-jobs` | `POST` | `matchApi.matchJobsForResume(id, params)` | [`frontend/src/api/matchApi.js:5`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/matchApi.js#L5) | `{ resume_id, top_k?, location_filter?, min_score? }` | `MatchResponse` (`matches`, `total_matched`, `threshold_applied`, `execution_time_ms`) |
| `/api/v1/matcher/batch-match` | `POST` | `matchApi.batchMatch(ids)` | [`frontend/src/api/matchApi.js:17`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/matchApi.js#L17) | `{ resume_ids: List[str] }` | `BatchMatchResponse` |
| `/api/v1/jobs/` | `GET` | `jobApi.getJobs(params)` | [`frontend/src/api/jobApi.js:4`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/jobApi.js#L4) | `?skip=0&limit=20&country=in` | `List[JobPostingResponse]` |
| `/api/v1/jobs/{job_id}` | `GET` | `jobApi.getJob(id)` | [`frontend/src/api/jobApi.js:12`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/jobApi.js#L12) | URL path `job_id` | `JobPostingResponse` |
| `/api/v1/jobs/stats` | `GET` | `jobApi.getStats()` | [`frontend/src/api/jobApi.js:17`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/jobApi.js#L17) | None | `{ "total": int, "by_source": dict, "by_country": dict }` |
| `/api/v1/jobs/refresh/status` | `GET` | `jobApi.getRefreshStatus()` | [`frontend/src/api/jobApi.js:22`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/jobApi.js#L22) | None | `RefreshStatusResponse` (`is_running`, `last_run`, `next_run`) |
| `/api/v1/jobs/refresh/trigger` | `POST` | `jobApi.triggerRefresh(sources)` | [`frontend/src/api/jobApi.js:27`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/jobApi.js#L27) | `{ sources: List[str] }` | `{ "status": "triggered" }` |
| `/api/v1/coach/skill-gap` | `POST` | `coachApi.getSkillGapReport(rId, jId)` | [`frontend/src/api/coachApi.js:5`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/coachApi.js#L5) | `{ resume_id, job_id }` | `SkillGapReport` (`readiness_score`, `critical_gaps`, `learning_roadmap`) |
| `/api/v1/coach/question-bank` | `POST` | `coachApi.getQuestionBank(rId, jId, opts)` | [`frontend/src/api/coachApi.js:15`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/coachApi.js#L15) | `{ resume_id, job_id, max_technical?, max_behavioral?, max_gap? }` | `QuestionBank` (`technical_questions`, `behavioral_questions`, `gap_questions`, `tips`) |
| `/api/v1/coach/evaluate-answer` | `POST` | `coachApi.evaluateAnswer(data)` | [`frontend/src/api/coachApi.js:31`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/coachApi.js#L31) | `{ question_id, question_text, target_skill, job_context, candidate_answer }` | `AnswerEvaluationResponse` (`score`, `grade`, `strengths`, `weaknesses`, `improved_answer`, `rubric_breakdown`) |
| `/api/v1/coach/session` | `POST` | `coachApi.startFullSession(rId, jId)` | [`frontend/src/api/coachApi.js:47`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/coachApi.js#L47) | `{ resume_id, job_id }` | `FullCoachingSessionResponse` |
| `/api/v1/market/salary-insights` | `POST` | `marketApi.getSalaryInsights(params)` | [`frontend/src/api/marketApi.js:5`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/marketApi.js#L5) | `{ title_query, location?, pay_period_filter? }` | `SalaryInsightsResponse` (`salary_band`, `top_paying_companies`, `narrative`) |
| `/api/v1/market/trending-skills` | `POST` | `marketApi.getTrendingSkills(params)` | [`frontend/src/api/marketApi.js:15`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/marketApi.js#L15) | `{ title_query?, location?, top_n? }` | `SkillDemandResponse` (`skills`, `narrative`, `total_postings_analysed`) |
| `/api/v1/market/demand-heatmap` | `POST` | `marketApi.getDemandHeatmap(params)` | [`frontend/src/api/marketApi.js:25`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/marketApi.js#L25) | `{ title_query?, top_n? }` | `DemandHeatmapResponse` (`locations`, `hottest_market`, `narrative`) |
| `/api/v1/market/role-overview` | `POST` | `marketApi.getRoleOverview(params)` | [`frontend/src/api/marketApi.js:34`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/marketApi.js#L34) | `{ title_query, location? }` | `RoleOverviewResponse` (`salary_band`, `top_skills`, `top_locations`) |
| `/api/v1/market/resume-positioning` | `POST` | `marketApi.getResumePositioning(id)` | [`frontend/src/api/marketApi.js:43`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/marketApi.js#L43) | `{ resume_id }` | `ResumePositioningResponse` (`percentile`, `recommendations`) |
| `/api/v1/chat/query` | `POST` | `chatApi.sendQuery(data)` | [`frontend/src/api/chatApi.js:5`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/chatApi.js#L5) | `{ query, resume_id?, job_id?, history? }` | `ChatQueryResponse` (`query`, `router_decision`, `response`, `sources`, `actionable_recommendations`, `suggested_followups`, `degraded?`, `match_unavailable?`) |
| `/api/v1/chat/classify-intent` | `POST` | `chatApi.classifyIntent(query)` | [`frontend/src/api/chatApi.js:16`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/api/chatApi.js#L16) | `{ query }` | `RouterDecision` (`intent`, `confidence`, `backend`, `low_confidence`, `fallback_used`) |
| `/api/v1/graph/role-pathway` | `GET` | **MISSING IN CLIENT** | [`app/api/v1/endpoints/graph.py:68`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/graph.py#L68) | `?role_name=...&candidate_skills=...` | `RoleProgressionResponse` (`role_name`, `target_roles`, `pathways`) |
| `/api/v1/graph/bridge-skills` | `GET` | **MISSING IN CLIENT** | [`app/api/v1/endpoints/graph.py:27`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/graph.py#L27) | `?from_role=...&to_role=...` | `SkillBridgeResponse` (`from_role`, `to_role`, `bridge_skills`) |
| `/api/v1/graph/career-pathway/{id}` | `GET` | **MISSING IN CLIENT** | [`app/api/v1/endpoints/graph.py:95`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/graph.py#L95) | URL path `candidate_id` | `CareerPathwayResponse` (`candidate_id`, `high_leverage_skills`, `reachable_roles`) |

---

## 2. Table of Unhandled or Under-Rendered Backend Fields

The table below catalogs backend schema fields returned by production endpoints that the frontend currently ignores, drops, or silently replaces with fallbacks:

| Endpoint | Backend Field | Data Type | Current Frontend Behavior | Required Honest Frontend Display |
|:---|:---|:---|:---|:---|
| `/api/v1/chat/query` | `degraded` | `Optional[str]` | Completely ignored. | Top warning banner: "System Degraded: {agent} node encountered an error; displaying honest partial response without fallback fabrication." |
| `/api/v1/chat/query` | `match_unavailable` | `bool` | Completely ignored. | Renders distinct notice: "Job matching service is temporarily unavailable. Check backend connections." |
| `/api/v1/chat/query` | `no_matching_jobs` | `bool` | Completely ignored. | Renders distinct notice: "Search executed successfully, but 0 matching jobs met qualification criteria in the database." |
| `/api/v1/chat/query` | `router_decision.low_confidence` | `bool` | Ignored. | Renders amber badge: "Low Confidence Routing" when true. |
| `/api/v1/chat/query` | `router_decision.fallback_used` | `bool` | Ignored. | Renders amber badge: "Fallback Route Used" when true. |
| `/api/v1/chat/query` | `router_decision.backend` | `str` ("trained", "heuristic") | Ignored. | Displays badge: "Router: scikit-learn model" or "Router: heuristic fallback". |
| `/api/v1/chat/query` | `sources[type=orchestrator_trace]` | `Dict` (`completed_nodes`, `retries`, `errors`) | Dropped in chat UI. | Collapsible Execution Trace inspector panel showing node sequence, latency, and retries. |
| `/api/v1/coach/skill-gap` | `critical_gaps[].learning_resources` | `List[Dict]` (`title`, `url`, `resource_type`, `provider`) | Not rendered. | Clickable links to official documentation when `url` is present; text without broken anchor when `url` is `null`. |
| `/api/v1/coach/question-bank` | `*.source` / `retrieved` | `bool` or `str` ("retrieved", "rule_based_fallback") | Ignored. | Badge on question card: "Corpus Retrieved" (emerald) vs "Rule-Based Fallback" (slate). |
| `/api/v1/coach/evaluate-answer` | `rubric_breakdown` | `Dict[str, float]` | Rendered as 4 linear progress bars; no radar chart. | Interactive Recharts `RadarChart` with accessibility `role="img"`, `aria-label`, and tabular fallback. |
| `/api/v1/market/trending-skills` | `skills[].demand_share` | `Optional[float]` | Ignored. | Display demand share percentage or "N/A" if null. |
| `/api/v1/market/trending-skills` | `skills[].velocity` | `Optional[float]` | Ignored. | Display velocity score or "N/A (baseline period)" if null. |
| `/api/v1/matcher/match-jobs` | `matches[].company_name` | `Optional[str]` | Partially defaulted to "Not specified", but needs strict consistency. | Strict "Not specified" text, never inventing dummy company names. |
| `/api/v1/matcher/match-jobs` | `matches[].location` | `Optional[str]` | Defaulted to "Location not specified". | Strict "Not specified" text, never inventing "Remote". |
| `/api/v1/graph/role-pathway` | Entire Endpoint | `RoleProgressionResponse` | Not integrated into UI. | Graph Career Pathway view in Market / Navigation. |

---

## 3. Complete Audit of Demo / Mock Data in the Frontend

| File & Line | Identifier / Construct | What It Contains | Under What Condition It Renders | Remediation R7 Action |
|:---|:---|:---|:---|:---|
| [`frontend/src/App.jsx:17`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/App.jsx#L17) | `import { demoResume } from "@/demo/demoData"` | Demo candidate profile ("demo-resume-001", Alex Morgan) | Imported at root level. | Retain import ONLY for explicit demo mode (`VITE_DEMO_MODE=true`). |
| [`frontend/src/App.jsx:44-55`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/App.jsx#L44-L55) | `handleSelectDemo` | Silent fallback: `catch { setActiveResume(demoResume) }` | Executes when backend `/resumes/demo-resume-001` fails. | **CRITICAL DEFECT REMOVED**: No silent fallback. Show honest error message unless `VITE_DEMO_MODE=true` is set. |
| [`frontend/src/demo/demoData.js:11-88`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/demo/demoData.js#L11-L88) | `demoResume` | Synthetic candidate resume (Alex Morgan, 4 skills, 1 project, 1 edu) | Injected when user clicks "Load Demo Profile". | Gate behind persistent top warning banner: `DEMO MODE ACTIVE: Using synthetic client-side profiles`. |
| [`frontend/src/demo/demoData.js:91-149`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/demo/demoData.js#L91-L149) | `demoMatches` | 2 synthetic job matches ("Nexus Innovations", "VectorStream Systems") with synthetic SHAP attributions | Loaded when `activeResume.isDemo` is true in `MatchesPage`. | Gate behind persistent demo banner; never render for real uploaded resumes. |
| [`frontend/src/pages/MatchesPage.jsx:28-44`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/pages/MatchesPage.jsx#L28-L44) | `fetchMatches` fallback | `if (activeResume?.isDemo) setMatches(demoMatches)` | Renders demo matches on demo profile or API error. | Restrict to explicit demo mode; for real profiles on error, render honest error banner and empty list. |
| [`frontend/src/components/coach/MockInterview.jsx:36`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/components/coach/MockInterview.jsx#L36) | `id: "DEMO-01"` | Fallback interview question text | Renders when no question bank passed to mock interview. | Replace with empty state prompting user to select or generate a real question bank. |
| [`frontend/src/data/mockData.js:1-18`](file:///c:/Users/mahim/Projects/ai-career-copilot/frontend/src/data/mockData.js#L1-L18) | Re-exports from `demoData.js` | Legacy mock aliases (`mockResumes`, `mockMatches`, `mockJobs`) | Unused in active components. | Retain as typed aliases for demo fixtures, gated by demo mode. |

---

## 4. Current Frontend Test Setup Analysis

### 4.1 Current Runner & Files
- **Runner**: Node.js built-in test runner (`node --test test/*.test.mjs`).
- **File**: `frontend/test/frontend_workflows.test.mjs` (19 test cases).

### 4.2 Defect in Current Tests (Finding 1)
The existing test file `frontend/test/frontend_workflows.test.mjs` does **not import any source code** from `frontend/src`:
- It defines an internal `const storage = { data: new Map(), ... }`.
- It defines an internal simulated interceptor function:
  ```javascript
  const token = localStorage.getItem("token")
  if (token) config.headers.Authorization = `Bearer ${token}`
  ```
- It simulates 401 handling inside the test body:
  ```javascript
  if (status === 401) { storage.removeItem("token"); ... }
  ```
- **Consequence**: Passing these 19 tests proves that the test writer knows how to write an `if` statement in JavaScript, but proves **zero correctness** about `frontend/src/api/client.js`, `frontend/src/context/AuthContext.jsx`, or any UI component.

### 4.3 Modernization Plan (Stage 5)
1. Install **Vitest** (`vitest`), `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, and `jsdom` pinned to versions released $\ge 14$ days ago.
2. Every test imports real source files from `frontend/src`:
   - `frontend/src/api/client.js`
   - `frontend/src/context/AuthContext.jsx`
   - `frontend/src/components/chat/CopilotChatDrawer.jsx`
   - `frontend/src/components/matches/JobMatchCard.jsx`
   - `frontend/src/components/coach/SkillGapReport.jsx`
   - `frontend/src/components/coach/InterviewRubricRadar.jsx`
   - `frontend/src/components/market/TrendingSkills.jsx`
3. Write $\ge 40$ real unit/component tests verifying honest state rendering, null-handling, radar fallback, and interceptor behaviors.
4. Demonstrate break-and-restore test failure on `client.js` 401 handler and `CopilotChatDrawer.jsx` degraded banner.
