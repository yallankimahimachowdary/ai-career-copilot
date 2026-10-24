# AI Career Copilot — Operational Runbook (Phase B / Remediation R14)

This runbook documents the exact, reproducible sequence of operational steps and commands to execute when real candidate resumes and human annotations are received.

---

## 1. Prerequisites and Environment Verification

Ensure Python 3.12 virtual environment is activated and backend services are active:

```powershell
# 1. Activate Virtual Environment
.\venv\Scripts\Activate.ps1

# 2. Verify Service Daemons
# - Ollama: http://localhost:11434 (llama3.2:3b pulled)
# - Neo4j: bolt://localhost:7687
# - PostgreSQL: localhost:5432
# - Gemini API Key: set in local untracked .env (GEMINI_API_KEY)

# 3. Verify Repository Integrity (7 Frozen Benchmark Hashes)
python -c "from scripts.run_all import verify_frozen_hashes; verify_frozen_hashes()"
```

---

## 2. Stage 1: Preparation & Annotation Sheet Generation (`--stage prep`)

### Step 2.1: Place Real Resumes
Place all real candidate resume PDFs into the designated, gitignored folder:
```
data/resumes_real/
```
> [!IMPORTANT]
> The folder must contain ONLY real candidate PDFs. If any synthetic test resume (`SYN_*` prefix or synthetic footer) is detected, the intake processor will refuse execution to prevent synthetic data contamination.

### Step 2.2: Execute Stage PREP
Run the staged prep runner:
```powershell
python scripts/run_all.py --stage prep --resumes-dir data/resumes_real --snapshot data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl
```

### Critical Operational Rules for Stage PREP:
1. **Build Universes ONCE and Freeze**:
   - Run universe generation exactly ONCE for the real run (`results/real/candidate_universes.json`).
   - Immediately compute and record its SHA-256 checksum in the run manifest and verification ledger.
   - Treat the generated universe file as frozen and read-only. Never re-run universe generation during evaluation to avoid any universe drift or seed variation across subsequent analysis passes.
2. **Manual Role Family Verification**:
   - Inspect `results/real/intake_report.json` and manually verify the role family classification (`Data/AI`, `Web/Software`, `Cybersecurity/Cloud`) for EVERY real candidate resume prior to generating or distributing annotation sheets.
   - Ensure borderline or interdisciplinary candidates are correctly assigned so raters evaluate candidates only against valid in-scope job universes.

### What Stage PREP Performs:
1. **Frozen Asset Verification**: Checks bit-for-bit SHA-256 match on all 7 benchmark files.
2. **Secret Scanner**: Ensures zero live credentials or API tokens are exposed in the repository.
3. **Backend Health Verification**: Probes Ollama, PostgreSQL, Neo4j, and Gemini API key status.
4. **Resume Intake (`scripts/intake_resumes.py`)**:
   - High-fidelity text extraction via PyMuPDF.
   - PII Scrubbing: Replaces candidate names with anonymous tokens (`Cand_001`, `Cand_002`) and strips contact info and institutional identifiers.
   - Zero-PII Regex Audit: Asserts zero email, phone, or name leaks in stored text.
   - Deterministic Taxonomy Parsing (Frozen Taxonomy v2.1).
   - Role Family Classification & In-Scope Screening (`Data/AI`, `Web/Software`, `Cybersecurity/Cloud`).
   - Produces `results/real/intake_report.json`.
5. **Stratified Universe Construction (`scripts/build_universes.py`)**:
   - Builds 60-job stratified universes per candidate (high-match, mid-match, hard-negative).
   - Allocates 8 double-rated resumes for inter-rater agreement.
6. **Annotation Sheet Generation (`scripts/make_annotation_sheets.py`)**:
   - Generates blinded CSV/JSON annotation sheets in `results/real/annotation_sheets/` with candidate names and method attributions blinded.
   - Writes `results/real/stage_prep_manifest.json`.
7. Concludes with status: `*** STATUS: AWAITING ANNOTATIONS ***`.

---

## 3. Human Annotation Workflow

1. Distribute the blinded sheets from `results/real/annotation_sheets/` to **Rater A** and **Rater B**.
2. Raters assign relevance grades (0 = Irrelevant, 1 = Relevant, 2 = Highly Relevant).
3. Collect the completed sheets and merge them into the canonical ground-truth JSONL file:
   ```
   results/real/labels.jsonl
   ```
   Format per row:
   ```json
   {"candidate_id": "Cand_001", "job_id": "adzuna_12345", "label": 2, "rater_id": "rater_a"}
   ```

---

## 4. Stage 2: Formal Evaluation & Table Generation (`--stage eval`)

Once `results/real/labels.jsonl` is in place, execute Stage EVAL:

```powershell
python scripts/run_all.py --stage eval --resumes-dir data/resumes_real --snapshot data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl --labels results/real/labels.jsonl --repeats 3
```

### What Stage EVAL Performs:
1. **Annotation Ingestion & Agreement**:
   - Validates label schemas.
   - Computes Quadratic Weighted Cohen's Kappa & Fleiss' Kappa with 1,000-sample bootstrap confidence intervals.
2. **Multi-Arm Ranking Pipeline & Precision@5 Policy**:
   - Evaluates BM25, SBERT (`sentence-transformers/all-MiniLM-L6-v2`), Skill Overlap, and Hybrid rankers.
   - **The P@5 Rule**: The primary `Precision@5` metric defines relevant items strictly as `rating = 2` (strong fit). Items with `rating >= 1` (partially relevant + strong fit) are computed and reported separately as a sensitivity column `P@5 (rel>=1, sens)`. Both columns appear in publication Table 1 and Table 2.
   - Computes nDCG@5, nDCG@10, MAP, MRR, Precision@5, and Recall@10 across 3 repeated runs for stability.
3. **Statistical Significance Testing**:
   - Paired Wilcoxon signed-rank tests (Hybrid vs BM25, Hybrid vs SBERT) with Holm-Bonferroni correction and 95% bootstrap CIs.
4. **Ablation Studies**:
   - Seniority gate ablation, skill-overlap removal, and LLM re-ranking evaluations.
5. **Publication Table Export**:
   - Exports formatted Markdown and CSV tables to `results/real/tables/`.
6. **Provenance Manifest**:
   - Writes `results/real/stage_eval_manifest.json` containing SHA-256 hashes of inputs, model weights, config, taxonomy, and tables.

---

## 5. End-to-End Dry-Run (Synthetic Test Pipeline)

To verify complete pipeline mechanics at any time without real data:

```powershell
python scripts/run_all.py --stage all-dryrun --max-resumes 3
```

- Operates on `data/resumes_dryrun/`.
- Every output file and row is tagged `run_type=dryrun`.
- Evaluates unlabeled ranker diagnostics (Kendall tau, top-k overlap, latency).
- Enforces strict quality-metric gating (`awaiting_real_annotations`), preventing any synthetic metric from entering paper tables.
- Writes `results/dryrun/stage_all_dryrun_manifest.json`.

---

## 6. Security and Compliance Rules

- **Zero Live API Calls**: Adzuna call counter (`data/ingest/adzuna_call_counter.json`) must remain locked at 20/20. No live network requests to Adzuna are permitted.
- **PII Protection**: Real PDFs and `results/real/` are gitignored. Never print, log, or commit candidate identities.
- **Frozen Benchmark Preservation**: Never edit `app/ranking/config.json`, `data/evaluation/*`, `data/router/test.jsonl`, `data/snapshots/jobs_snapshot_1_*.jsonl`, `docs/role_families_frozen.json`, or `docs/eval_scope.json`.
