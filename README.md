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
- Python 3.11 or 3.12
- Node.js 18+ and npm
- Docker Desktop (for PostgreSQL + pgvector and Neo4j)

### 1. Start Database Services (Docker Compose)
Launch PostgreSQL (with pgvector) and Neo4j:
```powershell
docker compose up -d postgres neo4j
```

### 2. Configure Environment Variables
Copy the template configuration file:
```powershell
Copy-Item .env.example .env
```
Open `.env` and set the required mandatory credentials:
- `SECRET_KEY`: A cryptographically secure random string (minimum 32 characters, e.g. generated via `openssl rand -hex 32`).
- `DATABASE_URL`: Asynchronous PostgreSQL connection string (e.g. `postgresql+asyncpg://copilot_dev_user:your_password@localhost:5432/ai_career_copilot`).
- `NEO4J_PASSWORD`: Strong password for Neo4j access (e.g. `your_neo4j_password`).

> **Note:** The backend strictly enforces credential presence at startup and rejects missing or whitespace-only keys.

### 3. Launch FastAPI Backend
```powershell
# Create and activate Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install reproducible dependencies
pip install -r requirements.txt

# Run database schema migrations
alembic upgrade head

# Start FastAPI server with live reload
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 4. Launch React Frontend
```powershell
# Navigate to frontend directory
cd frontend

# Install npm dependencies
npm install

# Start development server
npm run dev
```
- Open browser at: [http://localhost:3000](http://localhost:3000)
- The frontend connects to `http://localhost:8000` and automatically falls back to scrubbed offline demo data if the backend is not running.

---

## 🧪 Testing & Verification

### Backend Automated Test Suite
Run the full test suite using pytest:
```powershell
pytest tests/ -v
```

### Frontend Production Build & Linting
Verify frontend production build and code quality:
```powershell
cd frontend
npm run lint
npm run build
```

---

## 📜 License
Academic Research & Engineering Project — Vel Tech University (2024–2025).
