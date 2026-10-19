# Frozen Job Snapshot Runbook for Longitudinal Market Analysis

This runbook provides step-by-step instructions for reproducing, collecting, verifying, and comparing longitudinal job snapshots in **AI Career Copilot** using Windows PowerShell.

---

## 1. Prerequisites & Environment Check

Before initiating any snapshot cycle, verify system state and dependencies:

```powershell
# 1. Navigate to project root
cd C:\Users\mahim\Projects\ai-career-copilot

# 2. Activate Python virtual environment
.\venv\Scripts\Activate.ps1

# 3. Verify running services (PostgreSQL, Neo4j, Ollama)
python -c "
from scripts.take_snapshot import check_services
status = check_services()
print('Service Status:', status)
assert status['postgres'], 'PostgreSQL must be active!'
"

# 4. Check Adzuna Quota Counter & Call Budget
python -c "
from app.services.adzuna_quota_guard import adzuna_quota_guard
adzuna_quota_guard.print_quota_summary()
"
```

> [!IMPORTANT]
> - Ensure `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are configured in your local untracked `.env`.
> - **NEVER** print, log, echo, or commit credentials.
> - Verify that `calls_remaining` is sufficient to cover your planned query batch.

---

## 2. Taking Snapshot 2 (3 Weeks After Snapshot 1)

To evaluate market turnover and skill velocity without confounding variables, Snapshot 2 **MUST** be executed with **IDENTICAL settings** to Snapshot 1.

### Step 2.1: Verify Config Hash Consistency
Verify that `data/ingest/adzuna_queries_v1.json` has not been modified:
```powershell
(Get-FileHash -Path "data/ingest/adzuna_queries_v1.json" -Algorithm SHA256).Hash
# Expected: 1E794EB4AD5DBF292D92E7B13EC0994601410404EE28442AC124BE3F194061F7
```

### Step 2.2: Execute Snapshot Run
Run the snapshot tool specifying the semantic label `snapshot_2`:
```powershell
python scripts/take_snapshot.py --config data/ingest/adzuna_queries_v1.json --label snapshot_2
```
*Note: If you only wish to export existing database postings without making live API calls, add `--no-fetch`.*

### Step 2.3: Verification of Read-Only Protection & Manifest Emission
Confirm that the file was generated and locked:
```powershell
# 1. Check file attribute (should include R for Read-Only)
Get-Item data/snapshots/jobs_snapshot_2_*_adzuna.jsonl | Select-Object Name, Attributes, Length

# 2. Verify SHA-256 integrity against the manifest
python scripts/verify_snapshot.py snapshot_2
```

---

## 3. Comparing Snapshots (Longitudinal Turnover & Skill Shifts)

Execute the snapshot comparison script to calculate posting retention, new additions, expired vacancies, and skill count shifts:

```powershell
python scripts/compare_snapshots.py snapshot_1 snapshot_2
```

The script will report:
- Total unique postings in Snapshot 1 and Snapshot 2.
- Retained vacancies (intersection by `source_job_id`).
- New postings in Snapshot 2.
- Disappeared postings from Snapshot 1 (Turnover Rate: $\frac{\text{disappeared}}{\text{total}_1}$).
- Median and mean posting age at observation date.
- Absolute count shifts across all canonical skills (counts only; no causal claims).

---

## 4. Logging & Archival Ledger

Record the snapshot metadata in `snapshots/snapshot_log.csv`:

```csv
snapshot_id,date_taken,source,settings,posting_count,file_name,sha256,taken_by
snapshot_1,2026-10-19T11:45:00Z,adzuna_api,adzuna_queries_v1.json,675,jobs_snapshot_1_20261019_adzuna.jsonl,9D8...,teammate_1
snapshot_2,2026-11-09T11:45:00Z,adzuna_api,adzuna_queries_v1.json,682,jobs_snapshot_2_20261109_adzuna.jsonl,4F2...,teammate_2
```

### Backup Procedure
Store an encrypted offline backup of `data/snapshots/` on secure, access-controlled institutional storage:
```powershell
# Compress snapshot archive for offline storage (do not commit)
Compress-Archive -Path data/snapshots/*.jsonl -DestinationPath backups/snapshots_backup_$(Get-Date -Format 'yyyyMMdd').zip
```

---

## 5. Strict Operational Constraints ("What NOT To Do")

1. **DO NOT edit snapshot files**: Modifying even a single character in `data/snapshots/*.jsonl` breaks the cryptographic SHA-256 hash and invalidates the longitudinal study.
2. **DO NOT change query config between snapshots**: Modifying `adzuna_queries_v1.json` invalidates longitudinal comparison. `scripts/compare_snapshots.py` will refuse to compare snapshots with differing configuration hashes.
3. **DO NOT commit snapshot JSONL files**: Raw job postings are proprietary Adzuna data under their Terms of Service. `data/snapshots/*.jsonl` is `.gitignored`. Only the abstract manifest (`results/snapshots/manifest.jsonl`) is tracked.
4. **DO NOT share raw job text**: In accordance with Section 3 of the Adzuna API Terms of Service, raw text and contact details may not be redistributed. Share only aggregated statistical distributions and anonymized metrics.
5. **DO NOT exceed the API call budget**: Respect `ADZUNA_CALL_BUDGET`. Do not re-run failed queries repeatedly.
