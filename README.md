# AI Career Copilot 🚀
### An Explainable, Multi-Agent Retrieval-Augmented System for Personalized Career Guidance, Resume Optimization, and Interview Preparation

---

## 👥 Team

**Institution:** Vel Tech University, Chennai  
**Program:** B.Tech Artificial Intelligence and Data Science  
**Members:** Bala Maan Shree M & Yallanki Mahima Chowdary

---

## 🧠 System Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │    React 19 + Vite 8 Web Dashboard     │
                      │ (Tailwind CSS, Lucide, Recharts XAI)   │
                      └──────────────────┬─────────────────────┘
                                         │ HTTP REST / JSON
                                         ▼
                      ┌────────────────────────────────────────┐
                      │       FastAPI Gateway (/api/v1)        │
                      └──────────────────┬─────────────────────┘
                                         │
               ┌─────────────────────────┼─────────────────────────┐
               ▼                         ▼                         ▼
   ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
   │     Parser Agent     │  │    Matcher Agent     │  │     Coach Agent      │
   │  - PyMuPDF / docx    │  │  - pgvector Cosine   │  │  - Skill Diagnostics │
   │  - NLP Entity Rules  │  │  - BM25 + XGBoost    │  │  - QA Bank (STAR)    │
   │  - 384-dim MiniLM    │  │  - TreeSHAP XAI      │  │  - 0-10 Rubric Eval  │
   └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘
              │                         │                         │
              └─────────────────────────┼─────────────────────────┘
                                         ▼
                      ┌────────────────────────────────────────┐
                      │    Adaptive Query Intent Router        │
                      │       (/api/v1/chat/query)             │
                      │  - Strategy 1: Job Search & Match      │
                      │  - Strategy 2: Skill Progression Path  │
                      │  - Strategy 3: Interview STAR Coaching │
                      │  - Strategy 4: Macro Market Dynamics   │
                      └──────────────────┬─────────────────────┘
                                         │
                                         ▼
                      ┌────────────────────────────────────────┐
                      │           Data & Storage Tier          │
                      │  - PostgreSQL 16 + pgvector (384-dim)  │
                      │  - Neo4j 5 Graph DB (Skill-Role Graph) │
                      │  - ChromaDB (Local Dev Vector Store)   │
                      │  - Kaggle LinkedIn 4,000+ Postings     │
                      └────────────────────────────────────────┘
```

---

## 🛠️ Complete Technology Stack

### Backend Tier
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11 / 3.12, async SQLAlchemy 2.0)
- **Database & Storage**:
  - **Relational & Vector**: PostgreSQL 16 with [pgvector](https://github.com/pgvector/pgvector) for 384-dimensional dense semantic vectors.
  - **Graph Database**: Neo4j 5 Community for ontology representation and skill-role graph traversals.
  - **Local Development Store**: ChromaDB for rapid local semantic testing.
- **Dense Embeddings**: 384-dimensional dense embeddings via `sentence-transformers/all-MiniLM-L6-v2` with L2 unit normalization.
- **Lexical & Machine Learning Ranking**:
  - `rank-bm25` for lexical keyword relevance.
  - `xgboost` 2.0+ (GBDT Ranker & Regression) for multi-feature candidate scoring.
  - `shap` 0.44+ (`TreeExplainer`) for local feature attribution and explainable AI (XAI).
- **LLM Inference & Reranking**:
  - Local: Ollama (`llama3.2:3b`).
  - Cloud: Google Gemini (`gemini-2.0-flash` / `gemini-3.5-flash-lite`) and OpenAI (`gpt-4o-mini`).
- **Database Migrations**: Alembic.

### Frontend Tier
- **Framework**: [React 19](https://react.dev/) + [Vite 8](https://vite.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Motion & UI Primitives**: Framer Motion, Radix UI custom primitives
- **Visualizations**: [Recharts](https://recharts.org/) (TreeSHAP diverging attribution waterfall, salary distributions, radar rubrics)
- **Icons**: [Lucide React](https://lucide.dev/)
- **Data Flow**: Connects to the live FastAPI backend with graceful fallback to anonymized demo data (`frontend/src/demo/demoData.js`) for offline demonstration.

---

## 🔬 System Capabilities: Evaluated vs. Prototype Features

To maintain scientific integrity and transparent engineering standards, system components are divided into empirically evaluated pipelines versus interactive prototypes:

### 1. Empirically Evaluated Pipelines (Benchmark-Verified)
- **Phase B Ranking Pipeline**: Evaluated on held-out test splits with gold annotations, measuring Precision@K, NDCG@K, and MRR.
- **Feature Attribution & Explainability**: Local TreeSHAP contributions decomposing similarity, must-have requirements, experience penalties, and education bonuses into transparent explanations.
- **Counterfactual Robustness**: Synthetic counterfactual permutation tests verifying monotonicity under skill additions and experience shifts.
- **Baseline Parity**: Reproducible top-10 candidate retrieval validated against frozen experiment checkpoints.

### 2. Interactive & Prototype Features
- **Mock Interview Coach**: 3-step coaching pipeline (skill-gap diagnostic, STAR-format question generation, and rubric-based practice answer evaluation via LLM or rule-based fallback).
- **Macro Market Trends**: Industry compensation analysis, salary distributions, and market intelligence derived from LinkedIn postings.
- **Copilot Chat Drawer**: Intent-routed multi-turn conversational interface for job search and career roadmap recommendations.

---

## 🚀 Getting Started (Windows / PowerShell)

### Prerequisites
- **Python**: 3.11 or 3.12 (64-bit)
- **Node.js**: 18+ and npm
- **Docker Desktop** *(Optional for tests/offline demo, Required for live PostgreSQL & Neo4j)*: For PostgreSQL 16 (with pgvector) and Neo4j 5 Community.

> [!NOTE]
> If Docker is unavailable, the application test suite executes fully via FastAPI `AsyncClient` and dependency injection overrides. For live multi-agent database persistence, launch Docker Desktop before running Step 1.

---

### Step-by-Step Setup Sequence

#### 1. Create and Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### 2. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

#### 3. Configure Environment Variables
```powershell
Copy-Item .env.example .env
```
Open `.env` and verify credentials:
- `SECRET_KEY`: Cryptographically secure random secret (min 32 characters).
- `DATABASE_URL`: `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_career_copilot`
- `NEO4J_PASSWORD`: Neo4j password (e.g. `career_neo4j_2025`).
- `CORS_ORIGINS`: Includes `"http://localhost:3000"` and `"http://localhost:5173"`.

#### 4. Start Infrastructure Services (Requires Docker)
```powershell
docker compose up -d postgres neo4j
```

#### 5. Apply Database Migrations (Requires Database)
```powershell
alembic upgrade head
```
*(Head revision is `5e9f2b3c4d5a`)*

#### 6. Start FastAPI Backend
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Interactive API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Public Health Check: [http://localhost:8000/health](http://localhost:8000/health)

#### 7. Install Frontend Dependencies
```powershell
cd frontend
npm install
```

#### 8. Start Frontend Web Dashboard
```powershell
npm run dev
```
- Open browser at: [http://localhost:3000](http://localhost:3000) (or [http://localhost:5173](http://localhost:5173))
- Includes automatic fallback to anonymized demo data if backend is offline.

---

### 🧪 Step 9 — Automated Testing Suites

#### Backend Regression Suite
```powershell
# Run full regression suite (335+ tests)
pytest -q

# Run Phase 9 E2E integration verification
pytest tests/test_phase9_e2e_integration.py -v
```

#### Frontend Test Suite, Linting & Build
```powershell
cd frontend
# Run frontend unit tests (19 tests)
npm test

# Run Oxlint static analysis
npm run lint

# Build production bundle
npm run build
```

---

### 🔬 Step 10 — Evaluation & Benchmarking Scripts

All ranking and evaluation experiments preserve frozen ranking weights (`BM25: 0.10, SBERT: 0.10, Overlap: 0.80`).

#### 1. Query Intent Router Evaluation
```powershell
python scripts/eval_intent_router.py
```
*Evaluates 50 benchmark queries across 5 intent classes (job search, skill gap, resume feedback, career advice, interview prep).*

#### 2. RAG Grounding & Coach Evaluation
```powershell
python scripts/eval_rag_grounding.py
```
*Evaluates context recall, context precision, factual consistency, and grounding pass rate.*

#### 3. Fairness & Counterfactual Evaluation
```powershell
python scripts/evaluate_fairness_and_counterfactuals.py --seed 42 --repetitions 3
```
*Evaluates name-swap demographic invariance, counterfactual skill interventions, and ranking latency.*

#### 4. Ranking Evaluation & Ablations
```powershell
python scripts/evaluate_ranking.py --snapshot data/snapshots/test_snap_1.json --max-jobs 20
```
*Evaluates candidate retrieval against gold judgments with explicit missing-data handling.*

#### 5. Job Market Freshness CLI Refresh
```powershell
python -m app.services.job_refresh_coordinator
```
*Evaluates stale listing policies and coordinates resilient background market ingestion.*

#### 6. Repository Secret Scan
```powershell
python scripts/check_secrets.py
```
*Scans repository files for uncommitted credentials, private keys, or API tokens.*

---

## 📜 License
Academic Research & Engineering Project — Vel Tech University (2024–2026).
