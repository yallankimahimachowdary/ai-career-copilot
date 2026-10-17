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

## 4. Visualization Components: Production vs. Prototypes
- **Relevant Files:**
  - [`frontend/src/components/analytics/ShapWaterfall.jsx`](../frontend/src/components/analytics/ShapWaterfall.jsx)
  - [`frontend/src/components/analytics/SalaryDistribution.jsx`](../frontend/src/components/analytics/SalaryDistribution.jsx)
  - [`frontend/src/demo/demoData.js`](../frontend/src/demo/demoData.js)
  - [`README.md`](../README.md)
- **Status & Scope:**
  - The web frontend visualizes TreeSHAP feature attributions (diverging horizontal bars) and market compensation distributions (histograms) using Recharts.
  - Mentions of "radar rubrics" in historical documentation represent conceptual prototypes for multi-dimensional interview skill scoring. Interactive practice interview results are rendered via structured rubric progress bars and scorecards rather than polygonal radar plots.

---

## 5. Multi-Agent Orchestration Architecture
- **Relevant Files:**
  - [`app/services/router_service.py`](../app/services/router_service.py)
  - [`app/services/orchestrator.py`](../app/services/orchestrator.py)
- **Status & Scope:**
  - Intent classification and multi-agent coordination are executed via lightweight, asynchronous Python routing logic with strict Pydantic request/response schemas.
  - The system does not utilize heavy third-party workflow graph runtimes (e.g., LangGraph). Orchestration decisions (direct retrieval vs. skill gap analysis vs. interview preparation) are deterministic and testable without external graph runtime dependencies. LangGraph integration remains a planned future architecture exploration.

---

## 6. Fairness & Demographic Parity Evaluation
- **Relevant Files:**
  - [`app/ranking/fairness.py`](../app/ranking/fairness.py)
  - [`scripts/evaluate_fairness_and_counterfactuals.py`](../scripts/evaluate_fairness_and_counterfactuals.py)
- **Status & Scope:**
  - Demographic neutrality (name-swap perturbation invariance) and counterfactual skill intervention monotonicity are evaluated using purpose-built statistical tests (`scipy.stats.wilcoxon` and `kendalltau`).
  - The repository does not depend on the external `fairlearn` package. Disparate impact ratios and score stability metrics are computed directly through validated internal algorithms.

---

## 7. RAG Grounding & Hallucination Metrics
- **Relevant Files:**
  - [`app/evaluation/rag_eval.py`](../app/evaluation/rag_eval.py)
  - [`scripts/eval_rag_grounding.py`](../scripts/eval_rag_grounding.py)
- **Status & Scope:**
  - RAG evaluation for career coaching responses measures Context Recall, Context Precision, Factual Grounding Pass Rate, and Hallucination Count against gold reference datasets (`data/evaluation/rag_coach_eval_v1.json`).
  - These metrics are evaluated using deterministic, reproducible token-overlap and n-gram factual verification algorithms, rather than the external `ragas` library. This ensures zero API cost and deterministic benchmarking.

---

## 8. LLM Inference Costs & Offline Fallbacks
- **Relevant Files:**
  - [`app/services/llm_provider.py`](../app/services/llm_provider.py)
  - [`app/services/coach_service.py`](../app/services/coach_service.py)
  - [`app/services/parser_agent.py`](../app/services/parser_agent.py)
- **Status & Scope:**
  - When configured with Google Gemini (`GEMINI_API_KEY`) or OpenAI (`OPENAI_API_KEY`), the application makes external API calls that consume API credits subject to vendor rate limits and pricing.
  - Zero-Cost Operation: For fully local or cost-free deployments, the system natively supports local Ollama models (`llama3.2:3b`) or rule-based heuristic fallbacks. All automated unit and regression tests run without external network access or LLM credentials.
