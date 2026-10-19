# Adzuna API Integration Notes & Terms of Service Summary

This document records the official technical specifications, query parameters, returned schema, rate limits, and terms of service for the Adzuna Jobs API, retrieved and verified live on **October 19, 2026**.

---

## 1. API Architecture & Search Endpoint

- **Base URL:** `https://api.adzuna.com/v1/api`
- **Search Endpoint Path:** `/jobs/{country}/search/{page}`
  - Example (India, Page 1): `https://api.adzuna.com/v1/api/jobs/in/search/1`
- **HTTP Method:** `GET`
- **Country Code for India:** `in` (ISO 3166-1 alpha-2, verified in Adzuna Swagger spec `country` enum: `["gb", "us", "at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "in", "it", "mx", "nl", "nz", "pl", "sg", "za"]`).

### Mandatory Authentication Parameters (Query String)
- `app_id`: Application ID provided by Adzuna.
- `app_key`: Application Key / Secret provided by Adzuna.

> [!CAUTION]
> Authentication credentials travel in the query string (`?app_id=...&app_key=...`). To prevent secret leaks in logs, exception traces, or error monitors, URL queries must always be sanitized via a dedicated redaction helper before any logging or persistence.

---

## 2. Search Query Parameters & Constraints

| Parameter | Type / Format | Status in Swagger Spec | Behavior / Notes |
|:---|:---|:---|:---|
| `country` | string (path) | Required (enum includes `in`) | Country of interest. Set to `in` for India. |
| `page` | integer (path) | Required | 1-based page index. |
| `results_per_page` | integer (query) | Optional (min: 1, max: 50) | Number of postings per page. Documented maximum in Adzuna is 50. |
| `what` | string (query) | Optional | Free-text keyword search across title and description. |
| `what_and` | string (query) | Optional | All keywords must be found. |
| `what_phrase` | string (query) | Optional | Exact phrase match. |
| `what_exclude` | string (query) | Optional | Keywords to exclude. |
| `title_only` | string (query) | Optional | Keywords constrained strictly to job title. |
| `where` | string (query) | Optional | Geographic location centre (e.g. `Bengaluru`, `Hyderabad`, `Pune`, `Mumbai`, `Chennai`, `Delhi NCR`). |
| `distance` | number (query) | Optional | Search radius in kilometres (default 5km). |
| `sort_by` | string (query) | Optional (`default`, `hybrid`, `date`, `salary`, `relevance`) | Supported. Setting `sort_by=date` sorts by freshest postings. |
| `sort_dir` | string (query) | Optional (`up`, `down`) | Order direction. |
| `max_days_old` | integer (query) | Optional | Supported. Age limit in days (e.g., `max_days_old=30`). |
| `salary_include_unknown` | string (query) | Optional (`1`) | Returns jobs where salary is unspecified. |
| `full_time` / `permanent` | string (query) | Optional (`1`) | Employment type filters. |

---

## 3. Returned Fields & Payload Schema

From the OpenAPI / Swagger specification (`#/components/schemas/Job`), each job record in `results[]` contains:

| Field | Type | Description & System Mapping |
|:---|:---|:---|
| `id` | string | Unique ad identifier. Mapped to `source_job_id = id`, `external_id = "adzuna_" + id`. |
| `title` | string | Job title. Stored directly in `job_postings.title`. |
| `description` | string | **Truncated to 500 characters** by Adzuna API ("The details of the advertisement, truncated to 500 characters."). |
| `created` | string (ISO 8601) | Date posted (`YYYY-MM-DDTHH:MM:SSZ`). Parsed to UTC `job_postings.published_at`. |
| `redirect_url` | string | Outbound URL redirecting to advertiser. Stored in `job_postings.source_url`. |
| `company` | object (`Company`) | Contains `display_name`. Stored in `job_postings.company_name` (null when missing). |
| `location` | object (`Location`) | Contains `display_name` and `area` list. Stored in `job_postings.location` (null when missing). |
| `salary_min` | number | Minimum salary in local currency (INR for `in`). |
| `salary_max` | number | Maximum salary in local currency (INR for `in`). |
| `salary_is_predicted` | string / int (`"0"` or `"1"`) | Indicates whether salary was imputed by Adzuna's Jobsworth estimator. |
| `contract_time` | string (`full_time`, `part_time`) | Hours classification. |
| `contract_type` | string (`permanent`, `contract`) | Contractual classification. |
| `category` | object (`Category`) | Standard Adzuna sector categorization (`label`, `tag`). |
| `latitude`, `longitude` | number | Geographic coordinates. |

### Crucial Technical Constraints
1. **500-Character Description Truncation**:
   Adzuna does not return full job descriptions via the free search API; all descriptions are truncated to 500 characters. As a consequence:
   - Extracted canonical skills will be sparser per posting than scraped postings (which contain 2,000–5,000 characters).
   - Downstream models (SBERT embeddings, regex skill extractor) must process concise snippets without expecting lengthy qualification sections.
2. **Predicted Salary Handling**:
   When `salary_is_predicted == "1"` (or `1` / `True`), the salary values are synthetic estimations rather than employer disclosures. In compliance with data integrity policies:
   - Database columns `salary_min`, `salary_max`, `salary_currency` are stored as `NULL`.
   - The `salary_is_predicted` flag is preserved in frozen snapshot JSONL files for auditability.

---

## 4. Documented Rate Limits & Quota Guard

### Official Developer Portal Default Limits
From `https://developer.adzuna.com/docs/terms_of_service`:
- **Hits per minute:** 25
- **Hits per day:** 250
- **Hits per week:** 1,000
- **Hits per month:** 2,500

### Trial Plan / "Pending Activation" Account Constraints
- Newly created accounts under evaluation or pending activation have a hard lifetime limit of **25 total API test calls**.
- To prevent API exhaustion during live runs, the system enforces a strict client-side quota guard:
  - `ADZUNA_CALL_BUDGET = 20` (leaving a 5-call margin).
  - Every outgoing HTTP request (including retries and failed calls) increments a persistent file counter (`data/ingest/adzuna_call_counter.json`).
  - The provider refuses to dispatch any request if the counter reaches or exceeds `ADZUNA_CALL_BUDGET`.
  - Max 1 retry on transient network errors; **0 retries** on 4xx client errors.
  - Abort immediately on HTTP 429 (Too Many Requests) or HTTP 401/403 (Authentication failure).

---

## 5. Terms of Service & Redistribution Governance

- **Terms URL:** `https://developer.adzuna.com/docs/terms_of_service`
- **General Terms URL:** `https://www.adzuna.co.uk/terms-and-conditions.html`
- **Verification Date:** October 19, 2026.

### Permissible Use
Under Section 2 of Adzuna API Terms:
1. Publishing Adzuna ad listings (with required attribution).
2. Publishing Jobsworth salary estimates (with required Jobsworth badge).
3. Personal and academic research (with citation: "The Adzuna API" linking to the relevant domain).

### Academic & Research Use Clause
> *"Any other use of the Adzuna API by a commercial, government or academic organisation including any affiliates or individuals, is permitted subject to a 14 day trial period. This period is strictly for the purpose of validating the general coverage and quality of the data in addition to usability testing. It may not be used in its original format or in aggregation (including but not limited to vacancy counts, average salaries etc) to deliver any ongoing work or research, apart from the purpose stated prior, without written consent."*

### Storage and Redistribution Governance for This Project
1. **No Public Job Text Redistribution**:
   Raw Adzuna job descriptions and titles must **NEVER** be committed to Git or published in public repositories.
   - All snapshot files (`data/snapshots/*.jsonl`) are strictly `.gitignored`.
   - Only structural manifests (`results/snapshots/manifest.jsonl`) containing hashes, counts, and statistical aggregates are committed.
2. **Attribution & Outbound Links**:
   When displaying Adzuna jobs in user interfaces, the source must be acknowledged as "Adzuna" with outbound links referencing `redirect_url`.
3. **Snapshot Immutability**:
   Snapshots exported for academic reproducibility are set read-only (`attrib +R`), verified by cryptographic SHA-256 hashes, and stored offline.
