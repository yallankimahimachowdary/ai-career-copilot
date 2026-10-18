# Data Layer Design Specification (Phase R5)

## 1. Executive Summary & Objective

This document defines the schema and architectural design for the persistent data layer required by the AI Career Copilot thesis plan, addressing findings from an independent technical review. The implementation establishes:
1. Three relational PostgreSQL tables managed via Alembic: `evaluation_logs`, `learning_resources`, and `job_market_trends`.
2. A formalized Neo4j Knowledge Graph ontology introducing `Role` nodes, `REQUIRES`, `LEADS_TO`, and `OFFERS` relationships alongside existing `Skill` and `Company` nodes.
3. Population and query pathways for the Chroma vector collection `interview_material_embeddings`.
4. Clear documentation of deliberate architectural deviations from the initial thesis schema (`parsed_skills` and `match_scores` tables).

---

## 2. PostgreSQL Relational Schema

### 2.1 Table: `evaluation_logs`

Stores standardized, reproducible benchmark and experiment results across system components (e.g., router, parser, matcher, coach) without capturing any user identifiers or personal data.

- **Columns**:
  - `id`: `UUID`, Primary Key, default `gen_random_uuid()`
  - `created_at`: `TIMESTAMPTZ`, default `now()`, Not Null
  - `experiment_name`: `TEXT`, Not Null (e.g. `"router_held_out_benchmark"`, `"rag_grounding_eval"`)
  - `run_id`: `TEXT`, Not Null (e.g. UUID or timestamped identifier of the run)
  - `component`: `TEXT`, Not Null (e.g. `"intent_router"`, `"matcher"`, `"coach"`)
  - `metric_name`: `TEXT`, Not Null (e.g. `"macro_f1"`, `"accuracy"`, `"latency_p95"`)
  - `metric_value`: `DOUBLE PRECISION`, Not Null
  - `n_samples`: `INTEGER`, Nullable
  - `ci_low`: `DOUBLE PRECISION`, Nullable (confidence interval lower bound)
  - `ci_high`: `DOUBLE PRECISION`, Nullable (confidence interval upper bound)
  - `model_name`: `TEXT`, Nullable (e.g. `"multinomial_nb"`, `"llama3.2:3b"`)
  - `model_hash`: `TEXT`, Nullable (SHA-256 or truncated hash of model artifact)
  - `dataset_sha256`: `TEXT`, Not Null (SHA-256 hash of evaluation dataset file)
  - `git_commit`: `TEXT`, Nullable (Git SHA at evaluation time)
  - `seed`: `INTEGER`, Nullable (random seed for reproducibility)
  - `params`: `JSONB`, default `'{}'` (hyperparameters or evaluation arguments)
  - `notes`: `TEXT`, Nullable

- **Constraints & Indexes**:
  - Unique Constraint: `(run_id, component, metric_name)` (enforces idempotent metric logging)
  - Composite Index: `ix_evaluation_logs_exp_created` on `(experiment_name, created_at)`
  - Check / Privacy Rule: No `user_id` or candidate personal data is present in this table.

---

### 2.2 Table: `learning_resources`

Stores curated, validated learning materials mapped directly to canonical skills in the skill taxonomy (`app/core/taxonomy.py`).

- **Columns**:
  - `id`: `UUID`, Primary Key, default `gen_random_uuid()`
  - `skill_name`: `TEXT`, Not Null (must match canonical taxonomy name)
  - `title`: `TEXT`, Not Null (e.g. `"FastAPI Official Documentation"`)
  - `url`: `TEXT`, Nullable (only official project documentation or validated homepages; null if unverified)
  - `provider`: `TEXT`, Nullable (e.g. `"FastAPI / Tiangolo"`, `"Python Software Foundation"`)
  - `resource_type`: `TEXT`, Not Null, Check in `('official_docs', 'course', 'book', 'tutorial', 'practice')`
  - `difficulty`: `TEXT`, Not Null, Check in `('beginner', 'intermediate', 'advanced')`
  - `est_hours`: `NUMERIC(6, 2)`, Nullable (estimated completion hours)
  - `is_active`: `BOOLEAN`, default `true`, Not Null
  - `url_status`: `INTEGER`, Nullable (HTTP response status code, e.g. 200, 301, 404)
  - `url_checked_at`: `TIMESTAMPTZ`, Nullable (timestamp of latest live URL verification)
  - `source`: `TEXT`, Not Null, default `'curated_seed'`
  - `created_at`: `TIMESTAMPTZ`, default `now()`, Not Null

- **Constraints & Indexes**:
  - Unique Constraint: `(skill_name, title, provider)` (enforces idempotent seeding and loader upserts)
  - Index: `ix_learning_resources_skill_name` on `(skill_name)`
  - Index: `ix_learning_resources_is_active` on `(is_active)`

---

### 2.3 Table: `job_market_trends`

Captures aggregated, historical labor market intelligence per canonical skill across defined observation periods derived strictly from ingested job postings.

- **Columns**:
  - `id`: `UUID`, Primary Key, default `gen_random_uuid()`
  - `skill_name`: `TEXT`, Not Null (canonical skill token)
  - `period_start`: `DATE`, Not Null
  - `period_end`: `DATE`, Not Null
  - `period_type`: `TEXT`, Not Null, Check in `('snapshot', 'month')`
  - `postings_with_skill`: `INTEGER`, Not Null
  - `total_postings`: `INTEGER`, Not Null
  - `demand_share`: `DOUBLE PRECISION`, Not Null (fraction `postings_with_skill / total_postings`)
  - `source`: `TEXT`, Not Null (e.g. `"job_postings_aggregation"`)
  - `source_snapshot_sha256`: `TEXT`, Nullable (SHA-256 of underlying snapshot data)
  - `computed_at`: `TIMESTAMPTZ`, default `now()`, Not Null

- **Constraints & Indexes**:
  - Unique Constraint: `(skill_name, period_start, period_end, period_type, source)`
  - Index: `ix_job_market_trends_skill_period` on `(skill_name, period_start)`

- **Dynamic Derivation of Velocity**:
  - `velocity` (demand change rate over time, \(\Delta \text{demand\_share} / \Delta t\)) is **NOT** stored as a physical column in PostgreSQL.
  - Velocity is calculated dynamically at query time by ordering periods.
  - When fewer than 2 periods exist for a given skill, `velocity` is returned as `null` accompanied by an explicit explanation (`velocity_unavailable_reason = "Insufficient historical periods (minimum 2 required for velocity computation)"`).

---

## 3. Deliberately Omitted Tables (Thesis Schema Deviations)

The original conceptual thesis specification proposed two additional relational tables: `parsed_skills` and `match_scores`. These tables are **deliberately NOT added** to the relational database in this implementation:

1. **`parsed_skills`**:
   - *Rationale*: Candidate skill extraction is dynamic, evolving with parser iterations. Parsed skills, contact information, project technologies, and confidence scores are stored natively as structured JSONB within `Resume.parsed_data` and graph nodes (`(:Candidate)-[:HAS_SKILL]->(:Skill)`). Adding a separate normalized `parsed_skills` table would introduce data redundancy, synchronization overhead, and potential state drift without analytical gain.
2. **`match_scores`**:
   - *Rationale*: Hybrid job matching is computed per student query using a dynamic composite score (\(0.10 \times \text{BM25} + 0.10 \times \text{SBERT} + 0.80 \times \text{Overlap}\)) followed by XGBoost re-ranking and explainability (TreeSHAP). Job postings and student resumes are frequently updated or filtered by criteria (location, role, freshness). Storing transient match scores in a table would result in stale match records and massive table bloat.

Both deviations are documented in `docs/known_limitations.md`.

---

## 4. Neo4j Knowledge Graph Schema

The Neo4j graph is expanded to represent career progression and market demand structures without modifying or deleting existing `:Candidate`, `:Skill`, `:JobPosting`, or `:Company` nodes.

```mermaid
graph LR
    Role["(:Role {name, family, level, source})"]
    Skill["(:Skill {name})"]
    Company["(:Company {name})"]
    RoleB["(:Role (Target))"]

    Role -->|REQUIRES {importance, support_count, source}| Skill
    Role -->|LEADS_TO {typical_years_min, typical_years_max, source}| RoleB
    Company -->|OFFERS {postings, last_seen}| Role
```

### 4.1 Node Schema: `:Role`
- `name`: `String`, Unique (e.g. `"Backend Engineer"`, `"Senior DevOps Engineer"`)
- `family`: `String` (e.g. `"web_software"`, `"data_ai"`, `"cloud_devops"`, `"core_engineering"`, `"business_nontech"`)
- `level`: `String` (one of `"fresher"`, `"junior"`, `"mid"`, `"senior"`)
- `source`: `String` (`"curated_seed"`)

### 4.2 Relationship: `(Role)-[:REQUIRES]->(Skill)`
- Represents required skills for a role.
- Properties:
  - `importance`: `"core"` or `"nice"`
  - `support_count`: `Integer` or `null` (data-derived count from matching job postings)
  - `source`: `"curated_seed"` or `"derived_postings"`

### 4.3 Relationship: `(Role)-[:LEADS_TO]->(Role)`
- Represents plausible career progression pathways between roles within or across families.
- Properties:
  - `typical_years_min`: `Float` / `Integer`
  - `typical_years_max`: `Float` / `Integer`
  - `source`: `"curated_seed"`
- Constraint: Every non-senior role must have at least one outgoing `LEADS_TO` edge; self-loops are prohibited.

### 4.4 Relationship: `(Company)-[:OFFERS]->(Role)`
- Derived deterministically by mapping active `JobPosting` titles to normalized `Role` nodes.
- Properties:
  - `postings`: `Integer` (number of postings for this role by the company)
  - `last_seen`: `String` (ISO 8601 timestamp of most recent posting)

---

## 5. Chroma Vector Store (`interview_material_embeddings`)

The Chroma collection `interview_material_embeddings` is populated from an authored interview corpus (`data/interview_corpus/interview_corpus_v1.jsonl`).

- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, L2-normalized).
- **Document Text**: Concatenation of `question` and `key_points`.
- **Metadata**:
  - `corpus_id`: `String`
  - `role_family`: `String`
  - `question_type`: `String` (`"technical"`, `"behavioral"`, `"situational"`, `"hr"`)
  - `difficulty`: `String` (`"junior"`, `"mid"`, `"senior"`)
  - `skill_tags`: Comma-separated canonical skill names
  - `source`: `"authored"`

---

## 6. Migration & Rollback Strategy

1. **Single Alembic Migration**:
   - Created with `down_revision = '5e9f2b3c4d5a'` (the current migration head).
   - `upgrade()` creates `evaluation_logs`, `learning_resources`, and `job_market_trends` tables with their respective check constraints, indexes, and unique constraints.
   - `downgrade()` drops ONLY these three tables, leaving `users`, `resumes`, and `job_postings` completely untouched.
2. **Verification Protocol**:
   - Step A: Verify on a fresh scratch database (`ai_career_copilot_scratch`): upgrade head, downgrade -1, upgrade head, verify insert/select.
   - Step B: Apply upgrade head to development database (`ai_career_copilot`) after confirming Stage 0 pg_dump backup exists.
