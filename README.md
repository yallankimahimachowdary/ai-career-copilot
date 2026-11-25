# AI Career Copilot 🚀
### An Explainable, Multi-Agent Retrieval-Augmented System for Personalized Career Guidance, Resume Optimization, and Interview Preparation

---

## 👥 Team

**Institution:** Vel Tech University, Chennai  
**Program:** B.Tech Artificial Intelligence and Data Science  
**Members:** Bala Maan Shree M & Yallanki Mahima Chowdary

---

## ✨ What It Does

- **Resume parsing**: upload a PDF/DOCX and get a structured skill profile.
- **Explainable job matching**: ranked, India-focused job postings with TreeSHAP explanations of every score.
- **Interview coaching**: skill-gap diagnostic, STAR-style questions, and rubric-based answer evaluation.
- **Market insights**: role-level salary (INR), demand, and skills trends from live postings.
- **Copilot chat**: an intent-routed, multi-turn assistant that calls the right agent for each question.
- **Skill graph**: career pathways and bridge skills from a Neo4j skill-role graph.

---

## 🧠 System Architecture Overview

```mermaid
flowchart TD
    UI["React 19 + Vite 8 Dashboard<br/>Tailwind v4, light/dark theme, Recharts"]
    API["FastAPI Gateway (/api/v1)<br/>JWT auth"]
    ORCH["LangGraph Orchestrator + Trained Intent Router<br/>/api/v1/chat/query"]
    S1["S1 Job Search & Match"]
    S2["S2 Skill Progression Path"]
    S3["S3 Interview STAR Coaching"]
    S4["S4 Market Dynamics"]
    P["Parser Agent<br/>PyMuPDF/docx, taxonomy rules, MiniLM"]
    M["Matcher Agent<br/>BM25 + SBERT + skill overlap<br/>XGBoost + TreeSHAP"]
    C["Coach Agent<br/>rule-based gaps, STAR questions,<br/>0-10 rubric, radar chart"]
    K["Market Agent<br/>INR salary and skill trends"]
    LLM["LLM Provider Layer<br/>Ollama (default) | Gemini (switchable)"]
    DB[("PostgreSQL 16 + pgvector (384-dim)<br/>ChromaDB | Neo4j 5 skill-role graph<br/>Adzuna / scraped India job postings")]

    UI -->|"HTTP REST / JSON"| API --> ORCH
    ORCH --> S1 & S2 & S3 & S4
    S1 --> M
    S2 --> M
    S3 --> C
    S4 --> K
    ORCH --> P
    P & M & C & K --> LLM
    P & M & C & K --> DB
```

---

## 🛠️ Technology Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11 / 3.12, async SQLAlchemy 2.0)
- **Orchestration**: LangGraph, driven by a trained query-intent router
- **Auth & Access Control**: JWT, with per-user resume ownership checks
- **Databases**:
  - **Relational & Vector**: PostgreSQL 16 + [pgvector](https://github.com/pgvector/pgvector) (384-dim vectors)
  - **Vector Store**: ChromaDB (job postings and interview question corpus)
  - **Graph**: Neo4j 5 Community (Role / Skill / Company graph, bridge skills, career pathways)
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, L2-normalized)
- **Ranking & Explainability**:
  - `rank-bm25` lexical relevance
  - SBERT semantic similarity + taxonomy-based skill overlap
  - Fixed-weight hybrid ranker (BM25 0.10, SBERT 0.10, Overlap 0.80)
  - `xgboost` composite scorer + `shap` `TreeExplainer` for local attributions
  - Optional LLM re-ranker (JSON output, numbered job labels) and a claim verifier for explanation faithfulness
- **LLM Inference** (switchable via `LLM_PROVIDER`):
  - Local default: Ollama (`llama3.2:3b`)
  - Cloud alternative: Google Gemini (`gemini-3.5-flash-lite`, pinned model ID, no silent fallback in experiments)
- **Resume Parsing**: rule-based taxonomy parser is the default for uploads (`PARSER_MODE`); LLM parser is opt-in
- **Job Data**: Adzuna API provider with quota guard and frozen snapshots; optional `python-jobspy` scraper (off by default)
- **Migrations**: Alembic

### Frontend
- **Framework**: [React 19](https://react.dev/) + [Vite 8](https://vite.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/) with a blue "premium editorial" design system and a light/dark theme toggle
- **Motion & UI Primitives**: Framer Motion, Radix UI primitives
- **Visualizations**: [Recharts](https://recharts.org/) (TreeSHAP waterfall, salary distributions, interview rubric radar)
- **Icons**: [Lucide React](https://lucide.dev/)
- **Resilience**: honest loading, empty, and error states; falls back to anonymized demo data (`frontend/src/demo/demoData.js`) when the backend is offline

---

## 🔬 Evaluation & Scientific Integrity

All evaluation uses a **synthetic benchmark** (synthetic resumes and job postings, no real candidates, no human raters). Synthetic data is labelled as such in every script output and report. Known boundaries are documented in [docs/known_limitations.md](docs/known_limitations.md).

### Evaluated Components
- **Ranking pipeline**: BM25, SBERT, skill overlap, hybrid, hybrid + Ollama re-rank, and hybrid + Gemini re-rank, compared on a frozen job snapshot (nDCG@K, Precision@K, MRR).
- **Query intent router**: trained TF-IDF + logistic regression reaches **89.1%** accuracy on a locked 110-query synthetic test split (95% CI 82.7–94.5%), compared with 76.4% for zero-shot Ollama and 56.4% for regex rules.
- **Explainability**: local TreeSHAP contributions plus a claim verifier that checks LLM explanations against the resume.
- **Counterfactual and fairness tests**: skill-addition and experience-shift monotonicity, name-swap invariance, with positive controls.
- **Reproducibility**: frozen snapshot with SHA-256 hash, seeded runs, and git-tagged checkpoints.

### Known Caveats
- XGBoost is trained on **synthetic pseudo-labels** (a formula over the same features as the rule-based scorer plus noise), so it imitates the composite scorer rather than human judgment.
- Hybrid weights were tuned on a synthetic dev split and should be treated as provisional.
- Results come from a small synthetic dataset and are not claims about real-world hiring outcomes.

### Interactive Features
- **Mock Interview Coach**: deterministic skill-gap diagnostic, STAR question bank, and on-demand rubric evaluation (LLM or rule-based fallback).
- **Market Insights**: INR salary and demand analysis across Indian cities and domains.
- **Copilot Chat Drawer**: intent-routed multi-turn chat with markdown rendering.

---

## 🚀 Getting Started (Windows / PowerShell)

### Prerequisites
- **Python**: 3.11 or 3.12 (64-bit)
- **Node.js**: 18+ and npm
- **Docker Desktop**: required for live PostgreSQL 16 (pgvector) and Neo4j 5
- **Ollama**: with `llama3.2:3b` pulled (`ollama pull llama3.2:3b`)

> [!NOTE]
> Without Docker, the test suite still runs through FastAPI `AsyncClient` with dependency overrides. Start Docker Desktop before Step 4 for live persistence.

### Setup Sequence

#### 1. Create and Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### 2. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

#### 3. Configure Environment Variables
```powershell
Copy-Item .env.example .env
```
Edit `.env` (never commit it):
- `SECRET_KEY`: random secret, minimum 32 characters
- `DATABASE_URL`: `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_career_copilot`
- `NEO4J_PASSWORD`: your Neo4j password
- `LLM_PROVIDER`: `ollama` (default) or `gemini`
- `GEMINI_API_KEY` / `GEMINI_MODEL`: only if using Gemini (use the exact model ID, e.g. `gemini-3.5-flash-lite`)
- `PARSER_MODE`: rule-based (default) or LLM
- `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`: only for live Adzuna ingest
- `CORS_ORIGINS`: include `http://localhost:3000` and `http://localhost:5173`

#### 4. Start Infrastructure Services
```powershell
docker compose up -d postgres neo4j
```

#### 5. Apply Database Migrations
```powershell
alembic upgrade head
```

#### 6. Start FastAPI Backend
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Wait for `Application startup complete`.
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/health](http://localhost:8000/health)

#### 7. Install and Start the Frontend
```powershell
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000). The status dot should turn green when the backend is reachable.

#### 8. (Optional) Refresh Job Data
```powershell
# One-off scrape batch
python scripts/scraper/job_scraper.py --run-once

# Daily daemon
python scripts/scraper/job_scraper.py --schedule --run-on-start --daily-at-hour 2
```

---

## 🧪 Automated Testing

```powershell
# Backend regression suite (520+ tests)
pytest -q

# Frontend unit/component tests (47 tests), lint, and build
cd frontend
npm test
npm run lint
npm run build
```

---

## 📊 Evaluation & Benchmarking Scripts

All experiments keep the frozen hybrid weights (`BM25: 0.10, SBERT: 0.10, Overlap: 0.80`) and use a frozen job snapshot.

```powershell
# Intent router evaluation
python scripts/eval_intent_router.py

# RAG grounding and coach evaluation
python scripts/eval_rag_grounding.py

# Fairness and counterfactual evaluation
python scripts/evaluate_fairness_and_counterfactuals.py --seed 42 --repetitions 3

# Ranking evaluation and ablations
python scripts/evaluate_ranking.py --snapshot data/snapshots/test_snap_1.json --max-jobs 20

# Full ranking experiment runner (BM25 / SBERT / hybrid / LLM re-rank arms)
python scripts/run_ranking_experiment.py

# Parser evaluation against hand-labelled gold skills
python scripts/eval_parser.py

# Staged experiment pipeline (prep, eval, dry run)
python scripts/run_all.py --stage prep --resumes-dir <folder> --snapshot <snapshot.jsonl>

# Repository secret scan
python scripts/check_secrets.py
```

---

## 📁 Repository Layout

| Path | Purpose |
|---|---|
| `app/` | FastAPI app, agents, ranking, graph, orchestrator |
| `app/ranking/` | BM25, SBERT, overlap, hybrid, XGBoost wrapper, re-ranker, claim verifier |
| `frontend/` | React dashboard |
| `scripts/` | Scraper, evaluation, and experiment runners |
| `data/` | Snapshots and local ChromaDB (gitignored where large or private) |
| `docs/` | Known limitations, skill vocabulary, runbook, college report material |
| `tests/` | Backend regression suite |

---

## 📜 License
Academic Research & Engineering Project, Vel Tech University (2024–2026).
