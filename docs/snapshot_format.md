# Frozen Job Snapshot Format & Manifest Specification

This document defines the schema, storage format, cryptographic verification rules, and job-text truncation policies for frozen job snapshots in **AI Career Copilot** (Remediation R8).

---

## 1. Storage & Naming Convention

- **Directory:** `data/snapshots/` (strictly `.gitignored`; raw job postings must never be committed to source control).
- **File Format:** JSON Lines (`.jsonl`), UTF-8 encoded, exactly one JSON object per posting.
- **Naming Convention:**
  `data/snapshots/jobs_<label>_<YYYYMMDD>_adzuna.jsonl`
  - `<label>`: Semantic identifier (e.g., `snapshot_1`, `snapshot_2`).
  - `<YYYYMMDD>`: UTC date stamp of export (e.g., `20261019`).
- **File Protection:** Read-only attribute applied immediately upon creation (`attrib +R` on Windows, `chmod 444` on Unix). Existing snapshots with the same label or path cannot be overwritten.

---

## 2. Record Schema (JSONL)

Each line in the `.jsonl` snapshot contains an additive, backward-compatible JSON object:

| Field | Type | Description |
|:---|:---|:---|
| `id` | string | Internal database UUID. |
| `external_id` | string | Normalized identifier, e.g. `adzuna_12345678`. |
| `source_job_id` | string | Raw unique identifier from Adzuna API. |
| `title` | string | Job posting title. |
| `company` | string \| null | Employer display name (`null` if omitted, no synthetic defaults). |
| `location` | string \| null | Geographic locality display name (`null` if omitted, no synthetic defaults). |
| `description` | string | Raw job description text snippet (Adzuna truncates to 500 characters). |
| `posting_date` | string (ISO 8601) | Original posting date from Adzuna (`created`). |
| `source_url` | string \| null | Normalized redirect URL to advertiser. |
| `source` | string | Source provider label: strictly `"adzuna_api"`. |
| `work_type` | string | Employment schedule (`Full-time`, `Direct`). |
| `remote_allowed` | boolean | True if remote work is mentioned in description or location. |
| `skills` | list[string] | Canonical skill tokens extracted via canonical skills taxonomy. |
| `min_salary` | float \| null | Minimum salary in local currency (`null` if unstated or predicted). |
| `max_salary` | float \| null | Maximum salary in local currency (`null` if unstated or predicted). |
| `med_salary` | float \| null | Midpoint salary (`null` if unstated or predicted). |
| `pay_period` | string \| null | Salary frequency (`YEARLY`, or `null`). |
| `country` | string | Country name (`"India"`). |
| `currency` | string \| null | Currency code (`"INR"` or `null` if salary unstated/predicted). |
| `salary_is_predicted` | boolean | True if Adzuna Jobsworth imputed the salary. |
| `role_family` | string \| null | Seed role family classification (`data_ai`, `web_software`, etc.). |
| `city` | string \| null | Query city associated with search. |
| `embedding` | list[float] \| null | Dense vector (omitted by default; opt-in with `--with-embeddings`). |

---

## 3. Manifest Schema (`results/snapshots/manifest.jsonl`)

Every completed snapshot run appends exactly one line to `results/snapshots/manifest.jsonl` (tracked in Git, containing metadata and metrics but **zero job text**):

```json
{
  "label": "snapshot_1",
  "date_taken": "2026-10-19T11:45:00Z",
  "source": "adzuna_api",
  "config_sha256": "1E794EB4AD5DBF292D92E7B13EC0994601410404EE28442AC124BE3F194061F7",
  "snapshot_sha256": "...",
  "git_commit": "...",
  "package_versions": {
    "python": "3.12.10",
    "httpx": "0.28.1",
    "sqlalchemy": "2.0.38",
    "scikit-learn": "1.6.1",
    "sentence-transformers": "3.4.1"
  },
  "quota_limited": false,
  "call_budget": 20,
  "calls_used": 16,
  "counts": {
    "requests_used": 16,
    "fetched": 750,
    "unique": 680,
    "after_dedup": 675,
    "per_family": {
      "data_ai": 130,
      "web_software": 145,
      "cloud_devops": 135,
      "core_engineering": 125,
      "business_non_tech": 140
    },
    "per_city": {
      "Bengaluru": 210,
      "Hyderabad": 140,
      "Pune": 120,
      "Chennai": 95,
      "Mumbai": 60,
      "Delhi NCR": 50
    }
  },
  "null_rates": {
    "company": 0.02,
    "location": 0.01,
    "published_at": 0.00,
    "skills": 0.08
  },
  "skill_distribution": {
    "min": 0,
    "p25": 2,
    "median": 4,
    "p75": 6,
    "p90": 8,
    "max": 14,
    "share_with_at_least_one": 0.92
  },
  "description_lengths": {
    "min": 85,
    "median": 310,
    "p90": 490,
    "max": 500,
    "share_ge_100": 0.98,
    "share_ge_500": 0.12,
    "share_ge_1000": 0.00,
    "share_ge_2000": 0.00
  },
  "share_predicted_salary": 0.35,
  "terms_url": "https://developer.adzuna.com/docs/terms_of_service",
  "terms_retrieval_date": "2026-10-19",
  "tool_version": "1.0.0",
  "job_text_policy": {
    "adzuna_api_truncation": 500,
    "sbert_ranker_description_cut": 2000,
    "sbert_ranker_resume_cut": 2000,
    "llm_reranker_description_cut": 100,
    "llm_reranker_max_skills_shown": 6,
    "llm_reranker_candidate_pool": 20,
    "chroma_document_cut": 500,
    "embedding_provenance_formula": "Role: {title}\\nCompany: {company}\\nLocation: {location}\\nSkills: {skills}\\nDescription: {desc}"
  }
}
```

---

## 4. Job-Text Policies & Embedding Export Governance

1. **Embedding Vectors Bypass Guard**:
   In `app/ranking/baselines.py` (lines 190–194), `SBERTRanker` checks `if "embedding" in job and job["embedding"]:`. If a precomputed vector exists in the job dictionary, `SBERTRanker` uses it directly, bypassing its 2,000-character truncation policy.
   - To ensure consistent, reproducible evaluation, snapshots **do not export precomputed embeddings by default**.
   - The `--with-embeddings` CLI flag is strictly opt-in and explicitly logs vector provenance.
2. **Text Truncation Limits Across Codebase**:
   - `Adzuna API`: Truncates raw descriptions to **500 characters** upstream.
   - `SBERTRanker` (`app/ranking/baselines.py`): Truncates job description to **2,000 characters** and resume text to **2,000 characters**.
   - `LLMReranker` (`app/ranking/llm_reranker.py`): Truncates job description to **100 characters**, shows top **6 skills**, and limits evaluation pool to **top 20 candidate jobs**.
   - `Chroma Ingestion` (`scripts/ingest/adzuna_ingest.py`): Truncates combined title + description document to **500 characters**.
   - `PostgreSQL Vector Generation` (`embedding_service.construct_job_embed_text`): Concatenates `Role`, `Company`, `Location`, `Skills`, and `Description` passed to MiniLM-L6-v2 (effective model token limit: 256 tokens).
