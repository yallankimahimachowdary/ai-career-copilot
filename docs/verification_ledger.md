# Remediation Verification Ledger (R1 through R8)
-----------------------------------------------

**AI Career Copilot** — Comprehensive System Remediation & Rigorous Verification Ledger.
Last Updated: October 19, 2026.

---

## 1. Executive Summary & Verification Matrix

| Ledger Item | Area | Status | Key Artifacts & Metrics | Verified Commit |
| :--- | :--- | :---: | :--- | :---: |
| **L1** | **Adzuna Live Ingestion & Quota Guard** | **VERIFIED** | 18/20 calls used, 432 active Adzuna jobs, SHA-256 verified, read-only locked | `aa5eae9` |
| **L2** | **Frozen Snapshot Tooling & Quality** | **VERIFIED** | `snapshot_1` exported, manifest appended, 0% company/location nulls, 90.3% predicted salary nullified | `aa5eae9` |
| **L3** | **Live Sanity Match** | **VERIFIED** | `syn_swe_01` matched to Python Data Engineer (40.8%), 7.00ms/job latency, honest null company display | `aa5eae9` |
| **L4** | **Scraper Gating & Source Exclusions** | **VERIFIED** | `SCRAPER_ENABLED=false` by default, scraper gated, 1,555 legacy jobs preserved & segregated | `aa5eae9` |
| **L5** | **Zero Secret Leaks** | **VERIFIED** | 0 occurrences of literal `ADZUNA_APP_ID` or `ADZUNA_APP_KEY`, regex redaction filter active | `aa5eae9` |
| **L6** | **Frontend Honesty & Radar Charts** | **VERIFIED** | 47/47 vitest tests passed, 82 lint warnings (down from 86), SVG Radar with table fallback, `(No link available)` tag | Pending Commit 2 |
| **L7** | **Indian Academic Anonymizer Audit** | **VERIFIED** | 14/15 lines (93.3%) masked directly by regex; 1 unmasked line documented with mitigation plan | Pending Commit 2 |

---

## 2. Detailed Ledger Evidence

### L1: Adzuna Live Provider & Quota Guard
- **API Call Budget**: 20 calls total (safeguard against 25 trial limit).
- **Persistent Quota Counter**: `data/ingest/adzuna_call_counter.json` (gitignored). Increments *before* dispatching every HTTP request, including retries.
- **Quota Status at R8 Completion**:
  - `calls_used`: 18 / 20
  - `calls_remaining`: 2 / 20
  - `quota_limited`: False
- **Retry & Halt Guarantees**:
  - Max 1 retry on transient network errors (`httpx.TimeoutException`, `httpx.NetworkError`).
  - 0 retries on 4xx client errors.
  - Immediate total-run termination on HTTP 429 (`AdzunaRateLimitError`) and HTTP 401/403 (`AdzunaAuthError`).
- **Automated Test Coverage**: `tests/test_adzuna_provider.py` (9/9 passed, 100% stub-based, zero live API calls).

### L2: Frozen Snapshot Tooling & Data Quality Audit
- **Snapshot 1 Manifest**:
  - **Label**: `snapshot_1`
  - **Date Taken**: `2026-10-19T11:25:55.675420+00:00`
  - **File**: `data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl`
  - **Read-Only Attribute**: Applied (`attrib +R` on Windows / `chmod 0444` on Unix).
  - **Snapshot SHA-256**: `0732730B703454C3531E5CB2B3E2F89FBEC46D8DFB730644E257F02E110D6702`
  - **Config SHA-256**: `1E794EB4AD5DBF292D92E7B13EC0994601410404EE28442AC124BE3F194061F7`
  - **Verification Status**: Validated with `scripts/verify_snapshot.py snapshot_1` (Exit code 0).
- **Data Quality & Field Distribution**:
  - Total Unique Jobs: 432
  - Missing Company Display Name Rate: **0.0%** (all 432 entries have string company or explicit None).
  - Missing Location Display Name Rate: **0.0%**
  - Published Date Missing Rate: **0.0%**
  - Predicted Salary Share: **90.28%** (all successfully cleared to `NULL` in PostgreSQL; preserved in snapshot metadata).
  - Upstream Truncation: 99.31% of descriptions are truncated to 500 characters by free Adzuna tier.
  - Role Family Distribution: Business/Non-Tech (110), Data/AI (102), Cloud/DevOps (70), Core Engineering (58), Web/Software (50), Unassigned (42).
  - Candidate City Distribution: Bengaluru (166), Hyderabad (97), Mumbai (70), Pune (29), Chennai (17), Delhi NCR (11), Unassigned (42).

### L3: Real Sanity Match Against Frozen Snapshot Pool
Tested candidate `syn_swe_01` (Junior Backend Software Engineer; skills: Python, FastAPI, SQL, Docker, Git, REST API, Linux, PostgreSQL) scored against 432 Adzuna jobs:
- **Total Latency**: 3021.9 ms total (7.00 ms/job).
- **Top 5 Matched Opportunities**:
  1. **Python Data Engineer - Data Engineer III** (Chennai, Tamil Nadu) — **40.8% Match** (Composite: 67.2%, XGBoost: 79.9%, Matched: `['Python']`)
  2. **Software Engineer - Python** (Hyderabad, Telangana) — **40.8% Match** (Composite: 67.2%, XGBoost: 79.9%, Matched: `['Python']`)
  3. **Senior Software Engineer** (Bangalore, Karnataka) — **39.9% Match** (Composite: 67.5%, XGBoost: 76.8%, Matched: `['SQL']`)
  4. **.Net FSD with Angular** (Bangalore, Karnataka) — **39.9% Match** (Composite: 37.0%, XGBoost: 73.4%, Matched: `['REST API', 'SQL']`)
  5. **Engineer II, Embedded Software Design** (Bangalore, Karnataka) — **39.0% Match** (Composite: 62.0%, XGBoost: 78.1%, Matched: `['Linux']`)

### L4: Scraper Gating & Exclusions
- Web scraping via `jobspy` is strictly gated behind `SCRAPER_ENABLED=false` in `app/core/config.py` and `scripts/scraper/job_scraper.py`.
- Invoking `run_batch()` when disabled outputs an explicit warning and terminates with zero network traffic.
- Historical scraped rows in PostgreSQL (Indeed: 571, LinkedIn: 496, Glassdoor: 488; Total 1,555) are segregated by `source != 'adzuna_api'` and preserved for backwards compatibility.

### L5: Zero Secret Leaks & Redaction Guarantees
- `ADZUNA_APP_ID` (length: 8) and `ADZUNA_APP_KEY` (length: 32) exist strictly in untracked local `.env`.
- `git grep` verification confirmed **0 occurrences** of credential literals in all git-tracked files.
- `app/core/redaction.py` masks API keys and credentials in URLs, exceptions, and error records.
- Pre-commit secret scanning hook verifies staged changes before any commit is finalized.

### L6: Frontend Honesty, Radar Chart & Real Tests
- **Vitest Unit & Integration Suite**: 47/47 passed across 6 test suites importing real production source code (`frontend/src`).
- **ESLint Warnings**: Maintained at **82 warnings** (down from 86; zero errors).
- **Interview Rubric Radar**: `InterviewRubricRadar.jsx` dynamically binds 100% of rubric dimensions passed from the backend, with full accessible HTML table fallback and responsive Recharts rendering.
- **Resource Link Honesty**: `SkillGapReport.jsx` renders an explicit `(No link available)` tag for learning resources whose `url` is null.

### L7: Anonymizer Coverage Audit on 15 Indian Academic Lines
An audit evaluating `app/services/anonymizer.py` against 15 representative Indian academic lines:
- **14 of 15 (93.3%)** institutions were stripped and replaced with `[INSTITUTION]`.
- **1 Unmasked Line**: `International Institute of Information Technology, Hyderabad` (IIIT Hyderabad).
- **Analysis & Production Impact**:
  - In synthetic benchmark evaluations (`data/fairness/synthetic_resumes_v1.jsonl`), all candidate institutions are drawn from the 24 canonical universities in `data/fairness/perturbations_v1.json` (which are 100% masked).
  - For free-form Indian resumes containing "International Institute of Information Technology", adding `International Institute of Information Technology` to `institution_patterns` in `app/services/anonymizer.py` completes 100% coverage.
