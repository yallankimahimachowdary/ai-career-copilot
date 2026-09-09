# AI Career Copilot 🚀

An AI-powered Career Copilot designed to assist users in resume optimization, job matching, skills gap analysis, and personalized interview preparation.

---

## 🛠️ Tech Stack (Sprint 1)

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12)
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org/)
- **Configuration & Validation**: [Pydantic v2](https://docs.pydantic.dev/) & `pydantic-settings`
- **Database & ORM**: PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) & [SQLAlchemy 2.0 (Async)](https://docs.sqlalchemy.org/)
- **Caching & Brokers**: Redis 7
- **Database Migrations**: Alembic
- **Testing**: Pytest & `pytest-asyncio` + HTTPX
- **Containerization**: Docker & Docker Compose

---

## 📁 Project Structure

```
ai-career-copilot/
├── .env.example               # Template environment configuration
├── .env                       # Local environment file (git-ignored)
├── .gitignore                 # Standard Python / Docker ignores
├── Dockerfile                 # Python 3.12-slim container build
├── docker-compose.yml         # Multi-container local orchestration (Postgres, Redis, FastAPI)
├── requirements.txt           # Production and testing dependencies
├── README.md                  # Project documentation
├── app/
│   ├── __init__.py            # Package root (version 0.1.0)
│   ├── main.py                # FastAPI entry point, lifespan, CORS, and router mount
│   ├── core/                  # Core configurations and logging
│   │   ├── config.py          # Pydantic BaseSettings
│   │   └── logging.py         # Standardized logger
│   ├── api/                   # API versioning and routes
│   │   └── v1/
│   │       ├── api.py         # API v1 router aggregation
│   │       └── endpoints/
│   │           └── health.py  # Health check route (/api/v1/health)
│   ├── db/                    # Database session & engine
│   │   ├── base.py            # SQLAlchemy DeclarativeBase
│   │   └── session.py         # Async engine & get_db dependency
│   ├── models/                # SQLAlchemy ORM models
│   ├── schemas/               # Pydantic schemas (e.g. HealthCheckResponse)
│   └── services/              # Business logic, AI agents, LLM integrations
└── tests/
    ├── conftest.py            # Test fixtures & async client
    └── test_health.py         # Health check and root endpoint tests
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.12+
- Docker Desktop (for containerized PostgreSQL & Redis)

### 2. Local Setup (Virtual Environment)

1. Activate your virtual environment:
   ```powershell
   # Windows PowerShell
   .\venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Ensure `.env` is configured:
   ```powershell
   # By default, .env is copied from .env.example
   ```

4. Start the local FastAPI development server:
   ```powershell
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

5. Access interactive API documentation:
   - Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
   - Health Check: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

### 3. Docker Compose Setup

To start the full stack (PostgreSQL with `pgvector`, Redis, and the FastAPI application):

```powershell
docker compose up --build -d
```

Check container status:
```powershell
docker compose ps
```

View API logs:
```powershell
docker compose logs -f api
```

Stop services:
```powershell
docker compose down
```

---

## 🧪 Running Tests

Run the asynchronous test suite:
```powershell
pytest
```
