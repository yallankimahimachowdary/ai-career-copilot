# Environment & Dependency Specification

This document provides reproducible environment setup instructions, validated dependency pins, and test execution procedures for **AI Career Copilot**.

---

## 1. System Platform & Python Specification

- **Target Operating System:** Windows 10 / 11 (64-bit AMD64)
- **Validated Python Version:** `Python 3.12.10`
- **Package Manager:** `pip` (>= 24.0)

---

## 2. Environment Creation & Activation (Windows PowerShell)

Run the following commands in the repository root directory:

```powershell
# 1. Create a dedicated virtual environment
python -m venv .venv

# 2. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Upgrade pip to latest release
python -m pip install --upgrade pip
```

---

## 3. Dependency Installation

Install the exact verified and pinned dependency stack directly from [`requirements.txt`](../requirements.txt):

```powershell
pip install -r requirements.txt
```

To verify dependency tree consistency and ensure no unresolved conflicts exist:

```powershell
pip check
```

---

## 4. Validated Dependency Versions

The table below lists all core dependencies and their validated pins from the clean installation:

| Category | Package | Verified Version | Purpose |
|---|---|---|---|
| **Web & API** | `fastapi` | `0.143.2` | Core ASGI REST API framework |
| | `uvicorn[standard]` | `0.54.0` | High-performance ASGI production web server |
| **Configuration** | `pydantic` | `2.14.1` | Data validation and schema enforcement |
| | `pydantic-settings` | `2.16.0` | Environment settings management |
| | `python-dotenv` | `1.2.4` | Local `.env` parsing |
| **Databases** | `sqlalchemy[asyncio]` | `2.1.4` | Asynchronous ORM and SQL toolkit |
| | `asyncpg` | `0.32.0` | Fast PostgreSQL async driver |
| | `psycopg2-binary` | `2.9.13` | Sync PostgreSQL driver for migrations/tools |
| | `alembic` | `1.20.0` | Database schema migration engine |
| | `pgvector` | `0.5.1` | PostgreSQL vector extension bindings |
| | `neo4j` | `6.4.1` | Neo4j async graph database driver |
| **HTTP & Networking** | `httpx` | `0.28.1` | Async HTTP client for external AI APIs |
| **Testing** | `pytest` | `9.1.1` | Test framework and test runner |
| | `pytest-asyncio` | `1.4.0` | Asyncio test runner plugin |
| **Document Parsing & NLP** | `python-multipart` | `0.0.32` | Form data and multipart file upload handling |
| | `pymupdf` | `1.28.2` | High-fidelity PDF text and layout extraction (`fitz`) |
| | `pypdf` | `6.20.1` | Fallback PDF extraction engine |
| | `python-docx` | `1.2.0` | DOCX resume parsing and extraction |
| | `spacy` | `3.8.16` | Named entity recognition and text preprocessing (`en_core_web_sm`) |
| **Data & Modeling** | `pandas` | `3.0.6` | Tabular data processing and analytics |
| | `tqdm` | `4.70.1` | Experiment and processing progress bars |
| | `xgboost` | `3.4.1` | GBDT ranking and classification model |
| | `shap` | `0.54.1` | TreeSHAP explainability engine |
| | `scikit-learn` | `1.9.1` | Machine learning utilities and metrics |
| **Web Scraping & Batch** | `beautifulsoup4` | `4.15.0` | HTML parsing for job scrapers |
| | `apscheduler` | `3.11.3` | Periodic background task scheduling |
| | `python-jobspy` | `1.2.0` | Multi-board live job ingestion client |
| **Embeddings & Vector** | `chromadb` | `1.5.9` | Embedded vector database |
| | `sentence-transformers` | `6.1.0` | Neural semantic embeddings (`all-MiniLM-L6-v2`) |
| **Ranking & Math** | `rank-bm25` | `0.2.2` | BM25 lexical keyword ranking algorithm |
| | `numpy` | `2.5.4` | Numerical array computations |
| | `scipy` | `1.18.1` | Statistical significance testing (Wilcoxon, Kendall) |
| **Utilities** | `json-repair` | `0.64.0` | Resilient JSON decoding for LLM responses |
| | `nest-asyncio` | `1.6.0` | Nested event loop patch for asynchronous runners |
| **Orchestration** | `langgraph` | `0.2.76` | Cyclic state graph orchestrator with router-driven execution |

---

## 5. Verification & Test Execution

Run the complete test suite:

```powershell
pytest tests/ -q
```

**Validated Test Result:**
- **Baseline:** 176 passed, 0 failed, 0 skipped.
- **Duration:** ~4 minutes on AMD64 Windows platform.

Run secret scanning check:

```powershell
python scripts/check_secrets.py
```

---

## 6. Platform-Specific Considerations & Limitations

1. **Asyncpg Windows Event Loop:**
   - Under Python 3.12 on Windows, the default event loop policy is `WindowsProactorEventLoopPolicy`. All asynchronous database connections through `asyncpg` require proactor compatibility, which is handled automatically in `app.main` and `pytest.ini` (`asyncio_mode = auto`).
2. **C++ Build Tools for Native Wheels:**
   - Pre-compiled binary wheels are used for `xgboost`, `scipy`, `numpy`, `asyncpg`, `psycopg2-binary`, `onnxruntime`, and `torch`. A separate MSVC C++ build toolchain is not required for standard installation when using 64-bit Python 3.12 on Windows.
3. **Local Development Hostnames:**
   - When running the application locally on Windows (e.g. `uvicorn app.main:app`), PostgreSQL and Neo4j endpoints connect via `localhost:5432` and `localhost:7687`. When executing within Docker containers, services communicate over Docker bridge network hostnames (`postgres`, `neo4j`).
