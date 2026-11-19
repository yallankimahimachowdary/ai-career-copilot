# AI Career Copilot: Comprehensive Backend Architecture & Implementation Guide

> **Document Purpose**: This guide provides a complete, clear, code-cited reference of the entire backend system of **AI Career Copilot**. It is written in plain, accessible language for students presenting their Major Project to college guides and external evaluators. Every statement, algorithm, and formula directly cites the exact source code files and function names.

---

## 1. High-Level System Architecture

AI Career Copilot is designed as an **Explainable Multi-Agent Career Coaching & Job Matching Platform**. The backend is built using **FastAPI** (Python 3.12 asynchronous web framework) paired with a **Hybrid Multi-Database Architecture**:
1. **PostgreSQL 16 + pgvector**: Stores transactional records (users, resumes, job postings) and performs high-dimensional dense vector similarity search (384-dimensional dense semantic embeddings).
2. **Neo4j 5.23 (Knowledge Graph)**: Models career graphs, role hierarchies, skill prerequisites, and step-by-step learning roadmaps.
3. **Redis 7.2 (Cache)**: Provides fast in-memory caching for market intelligence and repeated query results.
4. **ChromaDB**: Acts as an in-memory/persistent vector database for document-level RAG knowledge chunks.

```
                    +------------------------------------+
                    |       Frontend (React + Vite)      |
                    +-----------------+------------------+
                                      | HTTP / REST (JWT)
                                      v
                    +------------------------------------+
                    |        FastAPI Backend Engine      |
                    |          (app/main.py: app)        |
                    +-----------------+------------------+
                                      |
         +----------------------------+----------------------------+
         |                            |                            |
         v                            v                            v
+------------------+        +-------------------+        +--------------------+
|   Parser Agent   |        |   Matcher Agent   |        | LangGraph Copilot  |
| (Rule + Taxonomy)|        | (Hybrid + XGBoost)|        | (Adaptive Router)  |
+--------+---------+        +---------+---------+        +---------+----------+
         |                            |                            |
         +----------------------------+----------------------------+
                                      |
      +-------------------------------+-------------------------------+
      |                               |                               |
      v                               v                               v
+------------------+        +-------------------+        +--------------------+
| PostgreSQL/pgvec |        |    Neo4j Graph    |        |   LLM Providers    |
| (app/db/session) |        | (app/services/    |        |  (Gemini / Ollama) |
| Relational/Vector|        |  graph_service.py)|        |  (llm_provider.py) |
+------------------+        +-------------------+        +--------------------+
```

---

## 2. Complete Backend Folder Structure & Map

| Directory Path | Role & Contents | Key Highlight |
| :--- | :--- | :--- |
| `app/api/` | REST API routes, routers, and dependency injection | Clean API versioning (`/api/v1/`) |
| `app/api/v1/endpoints/` | Route handlers organized by functional domain | `resumes.py`, `matches.py`, `coach.py`, `market.py`, `chat.py`, `auth.py` |
| `app/core/` | Global configuration, security, database init, and taxonomies | `config.py`, `security.py`, `taxonomy.py` |
| `app/db/` | Database sessions, engine lifecycle, and base models | `session.py`, `base.py` |
| `app/models/` | SQLAlchemy ORM table definitions | `user.py`, `resume.py`, `job_posting.py`, `audit_log.py` |
| `app/schemas/` | Pydantic data schemas, request/response validation contracts | `resume.py`, `matcher.py`, `coach.py`, `market.py`, `chat.py` |
| `app/services/` | Core business logic, autonomous agents, and ML pipelines | `parser_agent.py`, `matcher_service.py`, `coach_service.py`, `graph_orchestrator.py` |
| `app/ranking/` | Retrieval & ranking benchmark engines | `hybrid.py`, `baselines.py`, `performance.py` |
| `scripts/` | Dataset generation, benchmarking, evaluation, and verification | `college_report/`, `verify_frozen_hashes.py` |
| `data/` | Frozen benchmark snapshots, synthetic datasets, and test sets | `college_demo/`, `snapshots/` |

---

## 3. Component Deep Dive: Exactly Where Code Lives

### 3.1 Database Connections
* **PostgreSQL with pgvector**:
  * **File**: [`app/db/session.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/db/session.py)
  * **Engine Factory**: `engine = create_async_engine(settings.DATABASE_URL)`
  * **Session Factory**: `AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)`
  * **FastAPI Dependency**: `async def get_db() -> AsyncGenerator[AsyncSession, None]`
  * **Vector Type**: Stored via `mapped_column(Vector(384))` in [`app/models/resume.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/models/resume.py#L32) and [`app/models/job_posting.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/models/job_posting.py#L35).
* **Neo4j Graph Database**:
  * **File**: [`app/services/graph_service.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/graph_service.py)
  * **Driver Init**: `self.driver = AsyncGraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))`
  * **Functions**:
    * `get_role_hierarchy(role_title)`: Traverses role transitions and prerequisite relationships.
    * `get_skill_prerequisites(skill_name)`: Queries graph nodes connected by `[:REQUIRES_SKILL]` and `[:LEARNING_PATH]`.
    * `get_career_path(current_role, target_role)`: Computes shortest pathway using Cypher queries.
* **ChromaDB**:
  * **File**: [`app/services/vector_store.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/vector_store.py)
  * **Init**: `chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)`

---

### 3.2 Where API Endpoints Live
All API endpoints are mounted in [`app/api/v1/api.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/api.py) and registered into FastAPI in [`app/main.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/main.py#L75).

| Functionality | Endpoint URL | HTTP Method | Handler File & Function |
| :--- | :--- | :---: | :--- |
| **System Health** | `/health` | `GET` | [`app/api/v1/endpoints/health.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/health.py): `health_check()` |
| **User Login** | `/api/v1/auth/login` | `POST` | [`app/api/v1/endpoints/auth.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/auth.py): `login()` |
| **Resume Upload** | `/api/v1/resumes/upload` | `POST` | [`app/api/v1/endpoints/resumes.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/resumes.py): `upload_resume()` |
| **Get Resume** | `/api/v1/resumes/{id}` | `GET` | [`app/api/v1/endpoints/resumes.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/resumes.py): `get_resume()` |
| **Match Jobs** | `/api/v1/matches/resume/{id}` | `POST` | [`app/api/v1/endpoints/matches.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/matches.py): `match_jobs_for_resume()` |
| **SHAP Explainability**| `/api/v1/matches/compare/{res_id}/{job_id}` | `GET` | [`app/api/v1/endpoints/matches.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/matches.py): `compare_resume_and_job()` |
| **Skill Gap Diagnosis**| `/api/v1/coach/skill-gap` | `POST` | [`app/api/v1/endpoints/coach.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/coach.py): `skill_gap()` |
| **Interview Questions**| `/api/v1/coach/question-bank` | `POST` | [`app/api/v1/endpoints/coach.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/coach.py): `question_bank()` |
| **Role Overview** | `/api/v1/market/role-overview` | `POST` | [`app/api/v1/endpoints/market.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/market.py): `role_overview()` |
| **Salary Insights** | `/api/v1/market/salary-insights` | `POST` | [`app/api/v1/endpoints/market.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/market.py): `salary_insights()` |
| **Copilot Chat RAG** | `/api/v1/chat/query` | `POST` | [`app/api/v1/endpoints/chat.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/chat.py): `process_chat_query()` |
| **Classify Intent** | `/api/v1/chat/classify-intent` | `POST` | [`app/api/v1/endpoints/chat.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/api/v1/endpoints/chat.py): `classify_query_intent()` |

---

### 3.3 Where Resume Parsing & Extraction Live
* **Text Extraction**:
  * **File**: [`app/services/extractor.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/extractor.py)
  * **Function**: `extract_text_with_metadata(content, filename)`
  * **Mechanism**: Detects file extension (`.pdf`, `.docx`, `.txt`). For PDFs, uses PyMuPDF (`fitz`) to extract text and block positions. For DOCX, uses `python-docx`.
* **Privacy & PII Scrubbing**:
  * **File**: [`app/services/anonymizer.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/anonymizer.py)
  * **Function**: `anonymize_resume(resume_text)`
  * **Mechanism**: Uses Microsoft Presidio and regex patterns to mask candidate names, phone numbers, email addresses, and physical addresses to ensure fair matching.
* **Deterministic Rule-Based Parser (Taxonomy v2.1)**:
  * **File**: [`app/services/parser_agent.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/parser_agent.py)
  * **Main Function**: `ParserAgent.parse(raw_text, metadata)`
  * **Sub-functions**:
    * `_parse_with_rules(raw_text)`: Deterministic extraction using regex and boundary rules.
    * `_extract_name(raw_text, lines)`: Extracts candidate name from the top header lines using capitalized name heuristics.
    * `_extract_education(raw_text)`: Detects degrees (B.Tech, M.Tech, BS, MS, PhD) and university institutions.
    * `_extract_experience(raw_text)`: Identifies work experience blocks, job titles, and durations in years.
* **Canonical Skill Taxonomy**:
  * **File**: [`app/core/taxonomy.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/core/taxonomy.py)
  * **Dictionary**: `CANONICAL_SKILL_PATTERNS`: Over 100 strictly bounded regex patterns (`r"\bpython\b"`, `r"\bjava\b(?!\s*script)"`, `r"\b(javascript|js)\b"`).
  * **Function**: `extract_canonical_skills(text)` matches text strictly with word boundaries to eliminate sub-token false positives (e.g., prevents "C" from matching "CSS").
  * **Soft Skills Separation**: `SOFT_SKILLS` defines communication, leadership, problem solving, agile/scrum as growth attributes rather than technical rejection barriers.

---

### 3.4 Where Job Matching & Score Calculations Live
The platform implements two complementary ranking paths:

#### A. Production Scorer & XGBoost Reranker
* **File**: [`app/services/matcher_service.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/matcher_service.py)
* **Function**: `MatcherAgent.match_jobs_for_resume(resume_id, limit, db)`
* **Step 1 (Dense Vector Retrieval)**:
  Queries PostgreSQL pgvector using cosine distance (`<=>` operator) on 384-dimensional dense embeddings (`all-MiniLM-L6-v2`) to retrieve the top $K$ candidate job postings:
  $$\text{Cosine Similarity} = 1.0 - \text{Cosine Distance}$$
* **Step 2 (Feature Extraction)**:
  Extracts 8 quantitative alignment features:
  1. Dense semantic cosine similarity
  2. Canonical skill overlap ratio ($|\text{Resume} \cap \text{Job}| / |\text{Job}|$)
  3. Raw matched skills count
  4. Raw missing skills count
  5. Experience duration ratio ($\min(1.0, \text{CandExp} / \text{ReqExp})$)
  6. Degree level alignment (binary 1/0)
  7. Role family exact match (binary 1/0)
  8. Role family cross-domain penalty
* **Step 3 (Composite Formula)**:
  $$\text{Score}_{\text{composite}} = 0.50 \times \text{Cosine}_{\text{dense}} + 0.35 \times \text{Overlap}_{\text{skills}} + 0.15 \times \text{Exp}_{\text{ratio}}$$
* **Step 4 (XGBoost & SHAP Reranking)**:
  Passes the feature vector through a trained `XGBRegressor` ([`artifacts/models/matcher_xgboost.json`](file:///c:/Users/mahim/Projects/ai-career-copilot/artifacts/models/matcher_xgboost.json)) and uses `shap.TreeExplainer` to calculate local Shapley attribution values explaining *why* a job was ranked higher or lower.

#### B. Frozen Benchmark Hybrid Ranker
* **File**: [`app/ranking/hybrid.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/ranking/hybrid.py)
* **Class**: `HybridRanker(BaseRanker)`
* **Function**: `HybridRanker.rank(anonymized_resume, job_pool, k)`
* **Weights** (Frozen in [`app/ranking/config.json`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/ranking/config.json)):
  $$\text{Score}_{\text{hybrid}} = 0.10 \times \text{BM25}_{\text{norm}} + 0.10 \times \text{SBERT}_{\text{norm}} + 0.80 \times \text{Overlap}_{\text{norm}}$$
  where each constituent baseline score is min-max normalized into $[0.0, 1.0]$ via `_min_max_normalize()`.

---

### 3.5 Where Autonomous Agents & LangGraph Copilot Live
* **LangGraph Orchestrator**:
  * **File**: [`app/services/graph_orchestrator.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/graph_orchestrator.py)
  * **Class**: `LangGraphOrchestrator`
  * **State Graph Structure**:
    Uses LangGraph `StateGraph(AgentState)` compiled with nodes:
    1. `classify_intent`: Evaluates query semantics and selects execution strategy.
    2. `retrieve_context`: Queries PostgreSQL, Neo4j, or ChromaDB according to the strategy.
    3. `synthesize_answer`: Feeds retrieved context and chat history to the LLM.
* **Adaptive Query Intent Router**:
  * **File**: [`app/services/router_service.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/router_service.py)
  * **Class**: `RouterService`
  * **Model**: Calibrated TF-IDF vectorizer + Logistic Regression classifier with temperature scaling parameter $\tau = 0.33$.
  * **Intent Classes**:
    1. `JOB_SEARCH_AND_MATCH` -> Executes vector retrieval + SHAP match pipeline.
    2. `RESUME_FEEDBACK` -> Invokes parser diagnostic and skill-gap assessor.
    3. `INTERVIEW_COACHING` -> Queries Neo4j question bank and evaluation rubrics.
    4. `MACRO_MARKET_DYNAMICS` -> Queries compensation percentiles and hiring trends.
* **LLM Provider Abstraction**:
  * **File**: [`app/services/llm_provider.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/llm_provider.py)
  * **Factory**: `get_llm_provider(name)`
  * **Providers Supported**:
    * `GeminiProvider`: Google Cloud Gemini API (`gemini-3.5-flash-lite`), providing fast 1–2 second responses.
    * `OllamaProvider`: Local on-premise execution via Ollama (`llama3.2:3b`), running fully offline without external API dependencies.

---

## 4. Step-by-Step Data Flow: From Resume Upload to Results

```
[Student in Browser]
       │
       ▼ (1) Drag-and-drop resume PDF
[POST /api/v1/resumes/upload]
       │
       ▼ (2) extractor.py: PyMuPDF extracts raw text and section headers
       │
       ▼ (3) parser_agent.py: Rule-based parser applies Taxonomy v2.1 regex
       │     Extracts: candidate_name, degree, institution, experience, skills
       │
       ▼ (4) embedding_service.py: SentenceTransformer (all-MiniLM-L6-v2)
       │     Generates 384-dimensional dense vector representation
       │
       ▼ (5) Database Persistence:
       │     Stored in PostgreSQL table 'resumes' with pgvector embedding
       │
       ▼ (6) matcher_service.py:
       │     - pgvector cosine distance search retrieves candidate pool
       │     - Hybrid scoring (BM25 + SBERT + Skill Overlap)
       │     - XGBoost regressor scores alignment
       │     - TreeSHAP computes feature attributions (+/- contributions)
       │
       ▼ (7) coach_service.py & graph_service.py:
       │     - Neo4j queries missing prerequisite skills
       │     - Recommends active learning resources from database
       │
       ▼ (8) Results Returned as JSON to React Frontend:
             - Top matching jobs with percentage match scores
             - Interactive SHAP waterfall chart
             - Skill-gap radar chart & interview mock questions
```

---

## 5. College Project Viva / Defense FAQ Guide

### Q1: What makes this project an "Agentic AI" system rather than just a basic CRUD app?
**Answer**: A standard CRUD application simply stores and fetches rows from a database. AI Career Copilot is a multi-agent system where independent autonomous components perform specialized cognitive tasks:
1. The **Parser Agent** validates, scrubs PII, and extracts structured entities using deterministic taxonomy patterns.
2. The **Matcher Agent** computes multi-modal similarity across lexical (BM25), dense semantic (SBERT), and categorical dimensions, followed by machine learning re-ranking.
3. The **XAI Explainer** uses game-theoretic Shapley values (SHAP) so the user understands exactly why they matched.
4. The **LangGraph Orchestrator** maintains conversation state and dynamically routes user queries to the appropriate knowledge store without hardcoded `if-else` chains.

### Q2: Why did you use both PostgreSQL (pgvector) and Neo4j?
**Answer**: Different data models excel at different operations:
* **PostgreSQL + pgvector** handles relational user accounts, job postings, and high-dimensional nearest-neighbor vector search ($K$-NN).
* **Neo4j** is a native graph database that excels at multi-hop relational traversals. Career pathways and skill prerequisites (e.g. *Python $\rightarrow$ PyTorch $\rightarrow$ Deep Learning $\rightarrow$ Computer Vision Engineer*) are naturally modeled as directed graphs (`[:REQUIRES_SKILL]`, `[:PROMOTES_TO]`), which would require expensive recursive SQL joins in a relational database.

### Q3: Why is the Hybrid matching formula weighted 80% towards Skill Overlap and only 10% on BM25 and 10% on SBERT?
**Answer** (Referencing [`app/ranking/config.json`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/ranking/config.json)):
Dense embeddings (SBERT) capture broad topical domain semantics (e.g., recognizing that "Data Scientist" relates to "Machine Learning"), but they can suffer from semantic drift where buzzwords inflate the score. Skill overlap is an exact, verifiable requirement. By placing 80% weight on explicit skill alignment and 20% on semantic and lexical similarity, the platform guarantees that candidates possess the non-negotiable tools needed for the job while still rewarding contextual relevance.

### Q4: How is candidate privacy protected?
**Answer**: In [`app/services/anonymizer.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/anonymizer.py), the platform integrates Microsoft Presidio to scrub personally identifiable information (PII) like candidate names, email addresses, phone numbers, and physical addresses before generating embeddings and performing matching. This prevents algorithmic bias based on gender, ethnicity, or location.

### Q5: Can the application run completely offline without paying for cloud APIs?
**Answer**: Yes. The backend is designed with a provider-agnostic interface ([`app/services/llm_provider.py`](file:///c:/Users/mahim/Projects/ai-career-copilot/app/services/llm_provider.py)). By setting `LLM_PROVIDER=ollama`, the system runs local quantized models (`llama3.2:3b`) on CPU/GPU via Ollama. Embeddings (`all-MiniLM-L6-v2`) and the parser rules also execute 100% locally on-premise without external network access.
