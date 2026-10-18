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

## 7. Fairness Audits & Name-Swap Invariance
- **Relevant Files:**
  - [`app/ranking/fairness.py`](../app/ranking/fairness.py)
  - [`scripts/evaluate_fairness_and_counterfactuals.py`](../scripts/evaluate_fairness_and_counterfactuals.py)
- **Status & Scope:**
  - Demographic invariance audits evaluate score stability under candidate name substitutions (e.g., gender and cultural variants).
  - Crucially, the name-swap test changes fields no ranker reads (invariance holds by construction), because the underlying ranking features rely exclusively on extracted skills, project descriptions, and experience text, ignoring candidate personal names.
  - The repository does not utilize the external `fairlearn` package.

---

## 8. Multi-Agent Orchestration Architecture
- **Relevant Files:**
  - [`app/services/graph_orchestrator.py`](../app/services/graph_orchestrator.py)
  - [`app/services/orchestrator.py`](../app/services/orchestrator.py)
  - [`app/services/router_service.py`](../app/services/router_service.py)
  - [`app/api/v1/endpoints/chat.py`](../app/api/v1/endpoints/chat.py)
  - [`docs/orchestrator_graph.md`](../docs/orchestrator_graph.md)
- **Status & Scope:**
  - Multi-agent coordination is executed via a compiled LangGraph `StateGraph` (`app/services/graph_orchestrator.py`) driven directly by the trained intent router (`artifacts/models/intent_router_v1.joblib`).
  - Architecture: The graph maintains a typed shared state (`GraphState`), conditional edges corresponding strictly to target intent agent sets (`JOB_SEARCH`, `SKILL_GAP_ANALYSIS`, `INTERVIEW_PREPARATION`, `CAREER_ADVICE`, `RESUME_FEEDBACK`), and cyclic retry transitions for bounded retry (`MAX_NODE_RETRIES = 1`) on transient exceptions.
  - Resilience: Transient errors (timeouts, network resets) trigger bounded retry before graceful fallback, while permanent errors record an `AgentFailureRecord` and allow surviving nodes to complete with state preservation.
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
  - Backend integration tests use mocked database sessions; the migration test checks the chain only; no browser automation exists; frontend tests re-implement logic.
  - End-to-end tests exercise FastAPI endpoints with dependency injection overrides rather than live external PostgreSQL and Neo4j instances.
  - Frontend test suites execute with Node's native test runner (`node --test`) against unit assertions, without end-to-end browser drivers (e.g., Playwright or Cypress).

---

## 11. Visualization Components: Production vs. Prototypes
- **Relevant Files:**
  - [`frontend/src/components/analytics/ShapWaterfall.jsx`](../frontend/src/components/analytics/ShapWaterfall.jsx)
  - [`frontend/src/components/analytics/SalaryDistribution.jsx`](../frontend/src/components/analytics/SalaryDistribution.jsx)
  - [`frontend/src/demo/demoData.js`](../frontend/src/demo/demoData.js)
  - [`README.md`](../README.md)
- **Status & Scope:**
  - The web frontend visualizes TreeSHAP feature attributions (diverging horizontal bars) and market compensation distributions (histograms) using Recharts.
  - Mentions of "radar rubrics" in historical documentation represent conceptual prototypes for multi-dimensional interview skill scoring. Interactive practice interview results are rendered via structured rubric progress bars and scorecards rather than polygonal radar plots.

---

## 12. RAG Grounding & Hallucination Metrics
- **Relevant Files:**
  - [`app/evaluation/rag_eval.py`](../app/evaluation/rag_eval.py)
  - [`scripts/eval_rag_grounding.py`](../scripts/eval_rag_grounding.py)
- **Status & Scope:**
  - RAG evaluation for career coaching responses measures Context Recall, Context Precision, Factual Grounding Pass Rate, and Hallucination Count against gold reference datasets (`data/evaluation/rag_coach_eval_v1.json`).
  - These metrics are evaluated using deterministic, reproducible token-overlap and n-gram factual verification algorithms, rather than the external `ragas` library. This ensures zero API cost and deterministic benchmarking.

---

## 13. LLM Inference Costs & Offline Fallbacks
- **Relevant Files:**
  - [`app/services/llm_provider.py`](../app/services/llm_provider.py)
  - [`app/services/coach_service.py`](../app/services/coach_service.py)
  - [`app/services/parser_agent.py`](../app/services/parser_agent.py)
- **Status & Scope:**
  - When configured with Google Gemini (`GEMINI_API_KEY`) or OpenAI (`OPENAI_API_KEY`), the application makes external API calls that consume API credits subject to vendor rate limits and pricing.
  - Zero-Cost Operation: For fully local or cost-free deployments, the system natively supports local Ollama models (`llama3.2:3b`) or rule-based heuristic fallbacks. All automated unit and regression tests run without external network access or LLM credentials.
