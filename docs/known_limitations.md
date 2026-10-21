# Known Limitations & Architecture Notes

This document provides a transparent, technically precise accounting of known system boundaries, design choices, dependency fallbacks, and scope demarcations in **AI Career Copilot**.

---

## 1. Access Control & Authorization Hardening
- **Relevant Files:**
  - [`app/api/v1/endpoints/resumes.py`](../app/api/v1/endpoints/resumes.py)
  - [`app/api/v1/endpoints/matches.py`](../app/api/v1/endpoints/matches.py)
  - [`app/api/v1/endpoints/coach.py`](../app/api/v1/endpoints/coach.py)
  - [`app/api/v1/endpoints/job_postings.py`](../app/api/v1/endpoints/job_postings.py)
  - [`app/api/deps.py`](../app/api/deps.py)
- **Status & Scope:**
  - In earlier prototype sprints, endpoints permitted optional user credentials for ease of manual testing, which allowed unauthenticated access to uploaded resume metadata.
  - Remediated in R1/R2: Strict authentication dependencies (`get_current_active_user`) are enforced across all personal data routes. Resume and candidate operations enforce resource ownership (`enforce_resume_ownership`), returning `404 Not Found` when attempting to access resumes owned by other users or `401 Unauthorized` for anonymous requests.
  - Administrative operations such as `DELETE /api/v1/jobs/{job_id}` strictly require superuser privileges (`Depends(get_current_active_superuser)`). Non-superuser authenticated accounts receive `403 Forbidden`.

---

## 2. Text Extraction & Named Entity Recognition (NER) Provenance
- **Relevant Files:**
  - [`app/services/extractor.py`](../app/services/extractor.py)
  - [`app/services/parser_agent.py`](../app/services/parser_agent.py)
  - [`requirements.txt`](../requirements.txt)
- **Status & Scope:**
  - Text extraction from PDF documents utilizes PyMuPDF (`fitz`) as the primary high-fidelity engine, with automatic fallback to `pypdf` if PyMuPDF encounters rendering errors or is unavailable.
  - Resume entity parsing utilizes spaCy (`en_core_web_sm`) for candidate name extraction, alongside structured regular expression patterns.
  - Provenance Tracking: To prevent silent degradation, `extract_text_with_metadata` captures the active extraction engine (`PyMuPDF` vs. `pypdf`), and `parser_agent.parse` records `parse_metadata` (including `extractor` and `spacy_ner_available`) on every `ParsedResume` object.

---

## 3. Absence of In-Memory Redis Cache Service
- **Relevant Files:**
  - [`requirements.txt`](../requirements.txt)
  - [`app/core/taxonomy.py`](../app/core/taxonomy.py)
  - [`app/services/coach_service.py`](../app/services/coach_service.py)
- **Status & Scope:**
  - Although `redis==8.1.0` was historically included in `requirements.txt`, the application does not instantiate or connect to a Redis daemon or client.
  - All occurrences of `"Redis"` across the repository refer strictly to the database/caching technology skill keyword in the canonical skills taxonomy, job descriptions, test fixtures, and evaluation datasets.
  - Unused dependencies have been removed from `requirements.txt`. Caching of semantic embeddings is performed directly via vector similarity search in PostgreSQL (`pgvector`) and local ChromaDB.

---

## 4. Query Intent Routing & Development Set Measurement
- **Relevant Files:**
  - [`scripts/eval_intent_router.py`](../scripts/eval_intent_router.py)
  - [`scripts/train_intent_router.py`](../scripts/train_intent_router.py)
  - [`scripts/score_router_label_audit.py`](../scripts/score_router_label_audit.py)
  - [`app/services/router_service.py`](../app/services/router_service.py)
  - [`data/router/`](../data/router/)
  - [`data/evaluation/query_intent_benchmark_v1.json`](../data/evaluation/query_intent_benchmark_v1.json)
  - [`artifacts/models/intent_router_v1.joblib`](../artifacts/models/intent_router_v1.joblib)
- **Status & Scope:**
  - In earlier project phases, router accuracy was measured on the regex rules with use_llm=False on a 50-query development set (`data/evaluation/query_intent_benchmark_v1.json`). Because the heuristic regular expressions were tuned directly against these 50 queries, reported 100% scores reflected development overfitting rather than generalized classification accuracy.
  - Production routing initially defaulted unmatched queries directly to `job_search`.
  - In Remediation R3, the query intent router is upgraded to a trained scikit-learn TF-IDF + multinomial LogisticRegression classifier (`artifacts/models/intent_router_v1.joblib`) evaluated on a locked, held-out test split of 110 queries (`data/router/test.jsonl`, SHA-256: `6340BB8A778BDC19A65A7E72EEF8F771AD7AE4AC7A0889912DC50BC679335AD4`).
  - Held-Out Test Split Performance (110 balanced samples, 22 per class):
    - Overall Accuracy: **89.09%** (98/110)
    - Macro-F1 Score: **0.8920**
    - 95% Bootstrap Confidence Interval on Accuracy: **[82.73%, 94.55%]** (1,000 resamples, percentile method)
    - Mean Inference Latency: **2.34 ms** (p95: **2.96 ms**)
    - Majority Baseline Accuracy: **20.00%**
    - Hard Cases Accuracy (queries with secondary intents, n=18): **50.00%**
    - Statistical Significance: McNemar's test comparing trained classifier against the heuristic baseline yields $\chi^2 = 29.1667$ and $p = 6.64 \times 10^{-8}$, demonstrating a statistically significant performance advantage over the heuristic.
  - Heuristic Emergency Fallback: The regex rule-based router remains available as an automatic safety fallback (or via `ROUTER_BACKEND=heuristic`), exhibiting a measured test accuracy of **56.36%** and Macro-F1 of **0.5516**.
  - Label Noise Audit: An inter-annotator agreement protocol has been established with a 60-sample stratified audit file (`results/router_label_audit_sample.csv`) awaiting independent human verification, scored via `scripts/score_router_label_audit.py`.

---

## 5. Ranking Hybrid Weights & Ground-Truth Labels
- **Relevant Files:**
  - [`scripts/tune_hybrid_weights.py`](../scripts/tune_hybrid_weights.py)
  - [`app/ranking/config.json`](../app/ranking/config.json)
  - [`app/services/matcher_service.py`](../app/services/matcher_service.py)
- **Status & Scope:**
  - The frozen ranking weights (`BM25: 0.10, SBERT: 0.10, Overlap: 0.80`) were derived via grid sweep heuristic tuning: hybrid weights came from separation-maximisation without relevance labels and sit on the grid boundary.
  - Because human relevance labels were unavailable for large-scale candidate rankings, weights maximize discrimination distance rather than empirical NDCG against verified hiring outcomes.

---

## 6. XGBoost Matcher & Synthetic Training Signals
- **Relevant Files:**
  - [`scripts/train_xgboost_ranker.py`](../scripts/train_xgboost_ranker.py)
  - [`app/ranking/ranker.py`](../app/ranking/ranker.py)
  - [`data/training/`](../data/training/)
- **Status & Scope:**
  - The XGBoost matcher trains on a synthetic formula plus noise.
  - Training targets are generated from linear combinations of lexical match, vector cosine similarity, and keyword coverage with Gaussian perturbation, rather than historical recruiter callback or interview advancement records.

---

## 7. Fairness Audits, Fairlearn Metrics & Positive Controls
- **Relevant Files:**
  - [`scripts/evaluate_fairness_v2.py`](../scripts/evaluate_fairness_v2.py)
  - [`data/fairness/synthetic_resumes_v1.jsonl`](../data/fairness/synthetic_resumes_v1.jsonl)
  - [`data/fairness/perturbations_v1.json`](../data/fairness/perturbations_v1.json)
  - [`docs/fairness_rag_design.md`](../docs/fairness_rag_design.md)
  - [`results/fairness_v2.json`](../results/fairness_v2.json)
  - [`tests/test_fairness_eval.py`](../tests/test_fairness_eval.py)
- **Status & Scope:**
  - In earlier project iterations, demographic invariance audits evaluated candidate name substitutions exclusively on candidate name fields. Because no production ranker reads candidate personal names, reported invariance was $1.0$ by construction and could not fail.
  - In Remediation R6, the fairness evaluation harness was redesigned to include verified positive controls that **must fail** when ranking bias is present:
    - **Demographic Disparity**: Evaluated using the official `fairlearn` package (`fairlearn==0.15.0`). Computes Demographic Parity Difference (DPD) and Demographic Parity Ratio (DPR, threshold $\ge 0.80$). Production rankers with anonymization enabled achieve $\text{DPD} = 0.0$ and $\text{DPR} = 1.0$.
    - **Positive Control A (`DemographicBiasedRanker`)**: Injects deliberate scoring penalties and boosts across demographic groups. Verified to fail the audit ($\text{DPD} = 0.8333 > 0.10$, $\text{DPR} = 0.0 < 0.80$).
    - **Institution-Tier Fairness**: Evaluates 24 universities across 3 tiers (Tier 1 Elite, Tier 2 Public Flagship, Tier 3 Regional/Community). While production anonymization strips educational institutions to eliminate prestige bias ($\text{Tier Gap} = 0.0$), **Positive Control B (`InstitutionPrestigeBiasedRanker`)** intentionally penalizes non-elite schools and fails the prestige fairness threshold ($\text{Tier Gap} = 0.3725 > 0.05$, $\text{Tier DPR} = 0.0 < 0.80$).
  - **Sequential Orchestrator Heuristic Ranking Disclaimer**: In `app/services/orchestrator.py`, the sequential pipeline computes a local skill-overlap heuristic rather than invoking the full ML-based `matcher_service`. This is maintained for minimal-dependency sequential pipelines, while the primary production path in `app/services/graph_orchestrator.py` uses the full feature-extracted XGBoost ranker.

---

## 8. Multi-Agent Orchestration Architecture
- **Relevant Files:**
  - [`app/services/graph_orchestrator.py`](../app/services/graph_orchestrator.py)
  - [`app/services/orchestrator.py`](../app/services/orchestrator.py)
  - [`app/services/router_service.py`](../app/services/router_service.py)
  - [`app/api/v1/endpoints/chat.py`](../app/api/v1/endpoints/chat.py)
  - [`docs/orchestrator_graph.md`](../docs/orchestrator_graph.md)
  - [`results/graph_smoke_run_v3.json`](../results/graph_smoke_run_v3.json)
  - [`tests/test_graph_degradation.py`](../tests/test_graph_degradation.py)
- **Status & Scope:**
  - Multi-agent coordination is executed via a compiled LangGraph `StateGraph` (`app/services/graph_orchestrator.py`) driven directly by the trained intent router (`artifacts/models/intent_router_v1.joblib`).
  - Architecture: The graph maintains a typed shared state (`GraphState`), conditional edges corresponding strictly to target intent agent sets (`JOB_SEARCH`, `SKILL_GAP_ANALYSIS`, `INTERVIEW_PREPARATION`, `CAREER_ADVICE`, `RESUME_FEEDBACK`), and cyclic retry transitions for bounded retry (`MAX_NODE_RETRIES = 1`) on transient exceptions.
  - Resilience & Honest Degradation:
    - Transient errors (timeouts, network resets) trigger bounded retry before graceful fallback.
    - Honest Failure Reporting: All unranked arbitrary query fallbacks (`select(JobPosting).limit(4)`) and synthetic mock job payloads (e.g. "Databricks", "Stripe") were completely removed from `match_node` and `router_service`. If database matching or embedding lookup fails, the system marks `match_unavailable=True`, records the original error attributed to its target service (`host:port`), returns `matched_jobs=[]`, and `synthesize_node` explicitly states that matching is currently unavailable rather than fabricating postings.
    - Error Recovery Semantics: Error records have `recovered=True` ONLY if a subsequent bounded retry of that specific node succeeded; all unrecovered errors remain `recovered=False` and accurately cause `determine_execution_status` to report `"degraded: <failing_agent(s)>"`.
  - Database Session Hygiene & Transaction Isolation:
    - Any exception caught on an `AsyncSession` executes an immediate `await session.rollback()` prior to retry or handler return, eliminating `InFailedSQLTransactionError` cascades on subsequent queries.
    - Test isolation: Negative database constraint tests wrap inserts in `session.begin_nested()` savepoints, ensuring constraint violations rollback cleanly without leaving aborted transactions or polluting server logs.
  - Smoke-Run Verification History:
    - Smoke Run v1 (`results/graph_smoke_run.json`): Erroneously reported `"success"` across all intents despite 3 of 5 queries logging network connection refusal errors (`WinError 1225`) because the status aggregation rule did not inspect error payloads.
    - Smoke Run v2 (`results/graph_smoke_run_v2.json`): Revealed honest degradation where `JOB_SEARCH` and `SKILL_GAP_ANALYSIS` reported `degraded: match` due to an inner try/except block running `select(JobPosting).limit(4)` on an unrolled-back session, triggering `asyncpg.InFailedSQLTransactionError`.
    - Smoke Run v3 (`results/graph_smoke_run_v3.json`): Fully verified across 2 consecutive passes for all 5 canonical intents against live Ollama (`llama3.2:3b`), PostgreSQL (with pgvector), and Neo4j. All 5 intents achieved verified `"status": "success"` with 0 errors and 0 unrecovered failures.
  - Latency & Observability: Per-node execution latencies are measured and attached to the response metadata as an `orchestrator_trace`.
  - Backend Toggle: Controlled via `ORCHESTRATOR_BACKEND` (`"langgraph"` by default, with `"sequential"` fallback to the legacy linear pipeline).
  - Scope Limits: LangGraph StateGraph executes within the FastAPI process; distributed task broker execution (e.g. Celery / Ray) or multi-machine agent distribution is out of current scope.

---

## 9. Data Layer, Role Progression Graph & Curated Corpora
- **Relevant Files:**
  - [`alembic/versions/6f0a1b2c3d4e_add_data_layer_tables.py`](../alembic/versions/6f0a1b2c3d4e_add_data_layer_tables.py)
  - [`app/models/evaluation_log.py`](../app/models/evaluation_log.py)
  - [`app/models/learning_resource.py`](../app/models/learning_resource.py)
  - [`app/models/job_market_trend.py`](../app/models/job_market_trend.py)
  - [`app/services/graph_service.py`](../app/services/graph_service.py)
  - [`app/db/neo4j.py`](../app/db/neo4j.py)
  - [`app/db/chroma.py`](../app/db/chroma.py)
  - [`data/graph/role_graph_seed.json`](../data/graph/role_graph_seed.json)
  - [`data/learning/learning_resources_seed.json`](../data/learning/learning_resources_seed.json)
  - [`data/interview_corpus/interview_corpus_v1.jsonl`](../data/interview_corpus/interview_corpus_v1.jsonl)
  - [`docs/data_layer_design.md`](data_layer_design.md)
- **Status & Scope:**
  - **Curated Seed Role Ontology**: Seeded from `data/graph/role_graph_seed.json` (52 roles across Software Engineering, Data & AI, Cloud & DevOps, Product & Agile, and Cybersecurity; 53 directed `LEADS_TO` progression edges; 0 loops or orphan roles; typical years between 1 and 5). Progression paths represent curated standard industry milestones rather than exhaustive empirical career trajectories.
  - **Curated Learning Resources**: Seeded from `data/learning/learning_resources_seed.json` (76 resources spanning canonical skills: 69 active, 7 inactive). All active resources link to official documentation or verified educational platforms; inactive resources represent deprecations or placeholder guides.
  - **Curated Interview Corpus**: Seeded from `data/interview_corpus/interview_corpus_v1.jsonl` (157 questions across 5 role families, including 49 non-technical behavioral, situational, and HR questions, each with 3-6 rubric evaluation points and embedding vectors stored in Chroma collection `interview_material_embeddings`). The corpus was curated and synthesized by an AI assistant and has not been reviewed by an external domain expert panel.
  - **Evaluation Logs Persistence**: Implemented via the `evaluation_logs` table (migration `6f0a1b2c3d4e`), storing benchmark metrics, model parameters, and dataset provenance hashes (`dataset_sha256`) strictly for offline and automated evaluation tracking without storing personal identifiers or candidate-identifying data.
  - **Job Market Trends & Dynamic Velocity**: Implemented via the `job_market_trends` table (migration `6f0a1b2c3d4e`), populated from the current job postings snapshot (1,555 postings) with verified `source_snapshot_sha256`. Velocity is dynamically computed at query time by `market_agent.get_trending_skills` relative to the stored baseline rather than precomputed as static delta values.
  - **Intentional Omission of Skeletons**: Separate `parsed_skills` and `match_scores` tables were intentionally omitted from the schema. Candidate parsed skills are stored natively as structured JSON in `resumes.parsed_data`, and match scores are dynamically generated at ranking time by `matcher_service` and `ranker.py`, avoiding synchronization drift and schema redundancy.

---

## 10. Test Harness & Integration Mocking
- **Relevant Files:**
  - [`tests/test_phase9_e2e_integration.py`](../tests/test_phase9_e2e_integration.py)
  - [`tests/test_migrations.py`](../tests/test_migrations.py)
  - [`frontend/test/`](../frontend/test/)
- **Status & Scope:**
  - Backend integration tests use mocked database sessions; migration tests check chain consistency; no browser automation (e.g. Playwright/Cypress) is used.
  - End-to-end tests exercise FastAPI endpoints with dependency injection overrides rather than live external PostgreSQL and Neo4j instances.
  - In Remediation R7, frontend testing was completely overhauled: the legacy `frontend_workflows.test.mjs` (which simulated interceptors internally without importing app source) was replaced with 47 real component tests using Vitest, `@testing-library/react`, and JSDOM. Tests import real production modules (`client.js`, `CopilotChatDrawer.jsx`, `MatchDashboard.jsx`, `InterviewRubricRadar.jsx`, `RolePathwayViewer.jsx`, etc.) and verify DOM rendering, user interactions, error handling, and session expiration directly.

---

## 11. Visualization Components & Radar Rubrics
- **Relevant Files:**
  - [`frontend/src/components/analytics/ShapWaterfall.jsx`](../frontend/src/components/analytics/ShapWaterfall.jsx)
  - [`frontend/src/components/analytics/SalaryDistribution.jsx`](../frontend/src/components/analytics/SalaryDistribution.jsx)
  - [`frontend/src/components/coach/InterviewRubricRadar.jsx`](../frontend/src/components/coach/InterviewRubricRadar.jsx)
  - [`frontend/src/components/market/RolePathwayViewer.jsx`](../frontend/src/components/market/RolePathwayViewer.jsx)
  - [`README.md`](../README.md)
- **Status & Scope:**
  - The web frontend visualizes TreeSHAP feature attributions (diverging horizontal bars) and market compensation distributions (histograms) using Recharts.
  - In Remediation R7, the missing interview rubric radar chart was implemented in `InterviewRubricRadar.jsx`. Built using Recharts `RadarChart` (with `PolarGrid`, `PolarAngleAxis`, `PolarRadiusAxis`, and `Radar`), it plots candidate performance across Technical Accuracy, Depth, Structure, and Specificity. It complies with WCAG accessibility standards by providing `role="img"`, an explicit `aria-label`, and an accessible HTML table fallback for screen readers and test runners.
  - Graph-based career progression is visualized in `RolePathwayViewer.jsx`, rendering interactive sequence nodes, transition types (`lateral` vs `promotion`), and bridge skills queried from the Neo4j knowledge graph (`GET /api/v1/graph/role-pathway`).

---

## 12. RAG Retrieval & Generation Evaluation Harness
- **Relevant Files:**
  - [`scripts/eval_rag_retrieval.py`](../scripts/eval_rag_retrieval.py)
  - [`scripts/eval_rag_generation.py`](../scripts/eval_rag_generation.py)
  - [`scripts/score_rag_human_validation.py`](../scripts/score_rag_human_validation.py)
  - [`data/rag_eval/rag_queries_v1.jsonl`](../data/rag_eval/rag_queries_v1.jsonl)
  - [`results/rag_retrieval.json`](../results/rag_retrieval.json)
  - [`results/rag_generation.json`](../results/rag_generation.json)
  - [`results/rag_human_validation_sample.csv`](../results/rag_human_validation_sample.csv)
  - [`tests/test_rag_eval.py`](../tests/test_rag_eval.py)
- **Status & Scope:**
  - In earlier project iterations, RAG grounding metrics were derived from a limited 5-sample set without confidence intervals or retrieval ablation.
  - In Remediation R6, a comprehensive, zero-third-party-dependency RAG evaluation harness was constructed:
    - **Dataset**: 100 balanced queries across 4 categories (`interview_prep`, `learning_resources`, `role_progression`, `market_demand`) with verified zero leakage ($\text{Trigram Jaccard} = 0.0007 < 0.60$).
    - **Retrieval Ablation (100 queries, 1,000 bootstrap resamples)**:
      - Router-Driven Retrieval achieved Mean Reciprocal Rank (MRR) of **0.4587** (95% CI: [0.3740, 0.5420]) and Hit@1 of **0.40** (95% CI: [0.31, 0.49]).
      - Outperforms the Fixed Baseline (MRR: **0.3510**, Hit@1: **0.21**) by nearly 2x at top-1, with an over 3x gain in interview preparation queries (MRR **0.5200** vs. **0.1727**).
    - **$2 \times 2$ Factorial Generation Matrix**: Evaluates (Fixed vs. Router Retrieval) $\times$ (Local Ollama `llama3.2:3b` vs. Google Gemini `gemini-2.0-flash`). Measures in-house RAGAS metrics: Faithfulness, Answer Relevancy, Context Precision, and Context Recall.
    - **Self-Judging Bias Mitigation**: When an LLM evaluates its own generated responses, it exhibits systematic positive bias. The harness mitigates self-judging bias by utilizing objective sentence-transformer cosine similarity and deterministic claim extraction, supplemented by an exported stratified blinded human validation sample (`results/rag_human_validation_sample.csv`, scored via Cohen's kappa with `scripts/score_rag_human_validation.py`).

---

## 13. LLM Inference Costs & Offline Fallbacks
- **Relevant Files:**
  - [`app/services/llm_provider.py`](../app/services/llm_provider.py)
  - [`app/services/coach_service.py`](../app/services/coach_service.py)
  - [`app/services/parser_agent.py`](../app/services/parser_agent.py)
- **Status & Scope:**
  - When configured with Google Gemini (`GEMINI_API_KEY`) or OpenAI (`OPENAI_API_KEY`), the application makes external API calls that consume API credits subject to vendor rate limits and pricing.
  - Zero-Cost Operation: For fully local or cost-free deployments, the system natively supports local Ollama models (`llama3.2:3b`) or rule-based heuristic fallbacks. All automated unit and regression tests run without external network access or LLM credentials.

---

## 14. Frontend State Transparency & Honest Degradation
- **Relevant Files:**
  - [`frontend/src/App.jsx`](../frontend/src/App.jsx)
  - [`frontend/src/components/chat/CopilotChatDrawer.jsx`](../frontend/src/components/chat/CopilotChatDrawer.jsx)
  - [`frontend/src/components/matches/MatchDashboard.jsx`](../frontend/src/components/matches/MatchDashboard.jsx)
  - [`frontend/src/components/matches/JobMatchCard.jsx`](../frontend/src/components/matches/JobMatchCard.jsx)
  - [`frontend/src/components/coach/SkillGapReport.jsx`](../frontend/src/components/coach/SkillGapReport.jsx)
  - [`frontend/src/components/coach/QuestionBank.jsx`](../frontend/src/components/coach/QuestionBank.jsx)
  - [`frontend/src/components/market/TrendingSkills.jsx`](../frontend/src/components/market/TrendingSkills.jsx)
  - [`frontend/src/demo/demoData.js`](../frontend/src/demo/demoData.js)
- **Status & Scope:**
  - Prior to Remediation R7, frontend components contained catch handlers that silently substituted fake demo matches and mock market positioning data on network or backend service failures, obscuring outages and degraded states.
  - In R7, silent demo fallback was completely eliminated:
    - `frontend/src/demo/demoData.js` is isolated and only accessible when the user explicitly configures `VITE_DEMO_MODE=true`. When active, a persistent, prominent warning banner indicates simulated demo mode.
    - Matcher states are strictly differentiated: service outages display an honest error banner (`match_unavailable`), while empty result sets display an explicit `no_matching_jobs` notice rather than invented vacancies.
    - Missing job metadata (`company_name`, `location`) renders explicitly as `"Not specified"` rather than substituting synthetic defaults like `"Tech Employer"` or `"Remote"`.
    - Chat interactions render real backend execution traces, intent router badges (`backend`, `confidence`, `fallback_used`), and degraded execution warning banners naming failed pipeline nodes.
    - Market trends display dynamic demand share percentages and velocity deltas, explicitly displaying `N/A (single baseline period)` when velocity is undefined.
    - Interview coaching explicitly tags question provenance (`"Corpus Retrieved"` vs `"Rule-Based Fallback"`) and distinguishes verified external learning resources from unlinked skills (`"Self-study / Documentation"`).

---

## 15. Job Ingestion Gating & Adzuna Live Provider Quota
- **Relevant Files:**
  - [`app/services/adzuna_quota_guard.py`](../app/services/adzuna_quota_guard.py)
  - [`scripts/ingest/adzuna_ingest.py`](../scripts/ingest/adzuna_ingest.py)
  - [`scripts/scraper/job_scraper.py`](../scripts/scraper/job_scraper.py)
  - [`scripts/take_snapshot.py`](../scripts/take_snapshot.py)
  - [`scripts/verify_snapshot.py`](../scripts/verify_snapshot.py)
  - [`data/ingest/adzuna_queries_v1.json`](../data/ingest/adzuna_queries_v1.json)
  - [`docs/snapshot_format.md`](../docs/snapshot_format.md)
  - [`docs/snapshot_runbook.md`](../docs/snapshot_runbook.md)
- **Status & Scope:**
  - **Live Scraper Gating**: Real-time multi-platform web scraping (`jobspy`) carries inherent anti-bot fragility, IP throttling risks, and unversioned HTML drift. To preserve experimental reproducibility and prevent pipeline instability, web scraping is gated behind `SCRAPER_ENABLED=false` by default. Existing historical scraped rows (`indeed`, `linkedin`, `glassdoor`) are preserved in PostgreSQL for backward compatibility but are strictly segregated by `source != 'adzuna_api'` and excluded from frozen evaluation benchmarks.
  - **Live Adzuna API Quota Guard**: Live job ingestion is transitioned to the official Adzuna REST API under a strict quota controller (`ADZUNA_CALL_BUDGET=20` default). Outgoing HTTP requests increment a persistent atomic counter file (`data/ingest/adzuna_call_counter.json`) *before* sending.
  - **Single Retry & Rate-Limit Halt**: Retries are constrained to at most 1 attempt on transient network failures; 4xx client errors trigger zero retries; HTTP 429 or HTTP 401/403 triggers an immediate full-run termination.
  - **Description Truncation**: Free-tier Adzuna job descriptions are truncated upstream by Adzuna to 500 characters. Downstream skill extractors and embedding models operate within this 500-character window.
  - **Salary Flagging**: When Adzuna's `salary_is_predicted` flag is set to `"1"`, numeric salary columns in the database are cleared to `NULL` to avoid propagating unverified machine-generated estimations as factual recruiter salary bands.

---

## 16. Seniority Gating, Role-Family Coverage & Strict Provenance
- **Relevant Files:**
  - [`app/core/seniority.py`](../app/core/seniority.py)
  - [`app/core/provenance.py`](../app/core/provenance.py)
  - [`scripts/check_dataset_overlap.py`](../scripts/check_dataset_overlap.py)
  - [`scripts/experiment_runner.py`](../scripts/experiment_runner.py)
  - [`scripts/create_checkpoint.py`](../scripts/create_checkpoint.py)
- **Status & Scope:**
  - **Role Family Imbalance in Snapshot 1**: Auditing the 432 frozen jobs in `jobs_snapshot_1_20261019_adzuna.jsonl` reveals that only three role families possess $\ge 60$ jobs to form a complete 60-job universe: Data/AI (117 jobs), Web/Software (117 jobs), and Cybersecurity/Cloud (62 jobs). The remaining six role families (Mechanical with 20 jobs, Electrical with 16, Commerce/Finance with 14, Mobile/UI-UX with 7, Arts/Media with 2, and Civil with 0) have deficits and cannot fill an isolated 60-job universe without cross-family padding or supplemental ingestion.
  - **Snapshot 1 Company Naming Convention**: In `jobs_snapshot_1_20261019_adzuna.jsonl`, company display names are exported under the standardized key `"company"` (with 0.0% missing across all 432 records). If inspecting under the legacy internal ORM column name `"company_name"`, the key is null on export. Downstream consumers must read `rec.get("company") or rec.get("company_name")`.
  - **Seniority Boundary Rule ("Engineer II")**: Standalone Roman numeral classification categorizes Level I / Engineer I as entry/junior, while Level III+ / Senior is senior. "Engineer II" / "Level II" represents an intermediate stage (~2-4 years experience) and is strictly categorized as `mid`. It acts as a bridge role: compatible with junior candidates seeking upward progression and senior candidates, but junior candidates are strictly excluded from `senior` and `lead` roles.
  - **Model Alias Mismatch in Strict Mode**: Public cloud LLMs (such as Google Gemini) frequently alias model family identifiers (e.g. `gemini-3.5-flash` dynamically resolving to `gemini-3.6-flash` or newer). In non-strict mode, this mismatch is flagged in run provenance. In strict provenance mode, any alias mismatch raises `ModelAliasMismatchError` and terminates the run to avoid unversioned evaluation drift.

---

## 18. Taxonomy v2.1 Freeze & Evaluation Scope Demarcation
- **Relevant Files:**
  - [`app/core/taxonomy.py`](../app/core/taxonomy.py)
  - [`app/core/provenance.py`](../app/core/provenance.py)
  - [`docs/eval_scope.json`](../docs/eval_scope.json)
  - [`scripts/build_universes.py`](../scripts/build_universes.py)
  - [`scripts/eval_parser.py`](../scripts/eval_parser.py)
- **Status & Scope:**
  - **Taxonomy Tuning & Freeze**: The canonical skill patterns in `app/core/taxonomy.py` were expanded to 92 skills to capture common technical tools observed in resume corpora (`MongoDB`, `Power BI`, `Excel`, `Firebase`, `Redux`, `Bash`, `Splunk`, `Nmap`, `Wireshark`, `Terraform`, `Seaborn`, `Matplotlib`, `Tableau`, `STAAD Pro`, `PCB Design`). Soft skills (`Leadership`, `Teamwork`) were deliberately excluded from the taxonomy. This taxonomy is FROZEN as `TAXONOMY_VERSION = "v2.1"` (SHA-256 `34203073A38633314606663838D536C09F77E8C9C2507F1CEE98096DD98F2A1C`) for all real experimental runs. Provenance logging strictly tracks this version and hash; runs mixing taxonomy versions will fail validation.
  - **Evaluation Scope Restriction**: Real ranking evaluation is strictly restricted to resumes within the three viable role families defined in `docs/eval_scope.json`: `Data/AI`, `Web/Software`, and `Cybersecurity/Cloud`. Resumes from the remaining six deficit families (`Electrical`, `Mechanical`, `Civil`, `Commerce/Finance`, `Arts/Media`, `Mobile/UI-UX`) are flagged `out_of_scope_for_ranking_eval` and served with the honest `insufficient_matching_postings` response, rather than producing distorted ranking evaluations on truncated pools.

---

## 20. Human Annotation Protocol & Rater Workload Allocation
- **Relevant Files:**
  - [`scripts/make_annotation_sheets.py`](../scripts/make_annotation_sheets.py)
  - [`scripts/ingest_annotations.py`](../scripts/ingest_annotations.py)
  - [`docs/RUNBOOK.md`](../docs/RUNBOOK.md)
- **Status & Scope:**
  - **Candidate Universe Stratification**: For each evaluated candidate, a 60-job universe is constructed consisting of stratified buckets (high match, mid match, hard negative).
  - **Workload Partitioning**: Across the 41 in-scope resumes, tasks are divided between two human annotators (Rater A and Rater B).
    - **Rater A**: Evaluates 25 candidates $\times$ 60 jobs = 1,500 pairs.
    - **Rater B**: Evaluates 24 candidates $\times$ 60 jobs = 1,440 pairs.
    - **Total Pairs**: 2,940 pairwise ratings.
  - **Inter-Rater Agreement Sample**: 8 candidates (480 pairs) are systematically double-rated across both Rater A and Rater B to assess Quadratic Weighted Cohen's Kappa and Fleiss' Kappa with 1,000 bootstrap resamples. The 8 double-rated candidate resumes are:
    `SYN_004`, `SYN_010`, `SYN_011`, `SYN_012`, `SYN_025`, `SYN_026`, `SYN_031`, and `SYN_074`.

## 19. Role-Family Frozen Job Counts and Candidate Universe Provenance
- **Relevant Files:**
  - [`docs/role_families_frozen.json`](../docs/role_families_frozen.json)
  - [`docs/eval_scope.json`](../docs/eval_scope.json)
  - [`scripts/build_universes.py`](../scripts/build_universes.py)
  - [`scripts/check_dataset_overlap.py`](../scripts/check_dataset_overlap.py)
- **Status & Scope:**
  - **Job-Side Frozen Pool**: Classification of the 432 jobs in `jobs_snapshot_1_20261019_adzuna.jsonl` yields exactly 117 Data/AI, 117 Web/Software, and 62 Cybersecurity/Cloud postings (total 296 in-scope jobs). An earlier unpinned classifier report temporarily displayed 152/82/62 due to non-standardized regex routing; the deterministic classifier restores the canonical 117/117/62 distribution with zero run-to-run drift.
  - **Resume-Side Frozen Distribution**: `docs/role_families_frozen.json` defines the frozen distribution of the 95 synthetic resumes: 14 Data/AI, 12 Web/Software, 8 Cybersecurity/Cloud (34 primary in-scope candidates), plus 7 borderline candidates recognized in `candidate_universes.json` (yielding 41 total candidates).

## 21. RQ3 Job-Side Unsupported Claims Confounded by Upstream API and Prompt Truncation
- **Relevant Files:**
  - [`app/ranking/claim_verifier.py`](../app/ranking/claim_verifier.py)
  - [`app/ranking/llm_reranker.py`](../app/ranking/llm_reranker.py)
  - [`scripts/run_r13_suite.py`](../scripts/run_r13_suite.py)
- **Status & Scope:**
  - In RQ3 (Explanation Faithfulness), automated claim verification evaluates whether missing skills cited in model re-ranking explanations are explicitly required by the job posting description.
  - **Upstream Adzuna API Truncation**: As recorded in `results/snapshots/manifest.jsonl`, the Adzuna Search API truncates job descriptions upstream to a hard cap of 500 characters (99.31% of snapshot jobs are at this 500-character boundary).
  - **Downstream Prompt Truncation**: In [`app/ranking/llm_reranker.py`](../app/ranking/llm_reranker.py), description snippets in the prompt are truncated to 100 characters (`desc[:100]`) to ensure the 20-candidate prompt fits token limits and maintains predictable latency.
  - **Confounding Effect**: When an LLM re-ranker infers that a role requires foundational domain tools (e.g. Git, SQL, or Docker for an ML Engineer), the automated regex verifier flags these assertions as "job-side unsupported" if the truncated 500-char snapshot text does not literally contain those tokens. This is a direct artifact of upstream API and downstream prompt truncation rather than pure hallucination.
