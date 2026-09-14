# AI Career Copilot 🚀
### An Explainable, Multi-Agent Retrieval-Augmented System for Personalized Career Guidance, Resume Optimization, and Interview Preparation

---

## 👥 Team & Project Contributions

**Institution:** Vel Tech University, Chennai  
**Program:** B.Tech Artificial Intelligence and Data Science  

| Member | Core Responsibilities |
|---|---|
| **Bala Maan Shree M** | React 18 + Vite Frontend Dashboard, UI/UX Design, Adaptive Query Intent Router (`/chat/query`), API Gateway Integration, Text Extraction & Preprocessing |
| **Yallanki Mahima Chowdary** | Multi-Agent Orchestration Architecture, XGBoost Matcher Re-ranking Model, TreeSHAP Local Explainability, PostgreSQL `pgvector` Embeddings, Local LLM Benchmarking |

---

## 🧠 System Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │    React 18 + Vite Web Dashboard       │
                      │ (Tailwind CSS, shadcn/ui, Recharts XAI)│
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
   │  - NLP Entity Rules  │  │  - XGBoost Ranker    │  │  - QA Bank (STAR)    │
   │  - 1536-dim vectors  │  │  - TreeSHAP XAI      │  │  - 0-10 Rubric Eval  │
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
                      │  - PostgreSQL 16 + pgvector (Jobs/Emb) │
                      │  - Redis 7 (Caching & Rate Limiting)   │
                      │  - Kaggle LinkedIn 4,000+ Postings     │
                      └────────────────────────────────────────┘
```

---

## 🛠️ Complete Technology Stack

### Backend Tier
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11 / 3.12)
- **Database & Storage**: PostgreSQL 16 with [pgvector](https://github.com/pgvector/pgvector) & [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/)
- **Machine Learning**: `xgboost` 2.0+ (Ranker & Regression), `shap` 0.44+ (`TreeExplainer` for local attribution), `scikit-learn`
- **Embedding Vectors**: 1536-dimensional dense vectors via OpenAI `text-embedding-3-small` / Google Gemini with fallback L2 normalization
- **LLM Inference**: Hybrid cloud/local architecture (Google Gemini 1.5/2.0 API + Ollama `llama3.2:3b` / `phi3:mini`)
- **Task Queue & Caching**: Redis 7
- **Migrations**: Alembic

### Frontend Tier
- **Framework**: [React 18](https://react.dev/) + [Vite 8](https://vite.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Component Primitives**: Radix / shadcn/ui custom components
- **Visualizations**: [Recharts](https://recharts.org/) (TreeSHAP diverging attribution waterfall, salary percentiles, radar rubrics)
- **Icons**: [Lucide React](https://lucide.dev/)
- **File Upload**: `react-dropzone` with client-side PDF validation

---

## 🚀 Getting Started

### 1. Start Database Services (Docker Compose)
Ensure Docker Desktop is running, then execute:
```powershell
docker compose up -d postgres redis
```

### 2. Launch FastAPI Backend
```powershell
# Create & activate Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt

# Run database schema migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 3. Launch React Frontend
```powershell
cd frontend
npm install
npm run dev
```
- Open browser at: [http://localhost:3000](http://localhost:3000)
- The frontend features an **offline demonstration mode** (`mockData.js`) that operates seamlessly even when the backend is offline.

---

## 🧪 Testing

Run the automated test suite:
```powershell
pytest tests/ -v
```

---

## 📜 License
Academic Research & Engineering Project — Vel Tech University (2024–2025).
