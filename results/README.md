# Tracked Research Results

This directory is reserved strictly for **scrubbed, anonymized research benchmark outputs, evaluation metrics, and summary tables** required to substantiate Phase B and thesis results.

## Privacy & Anonymization Policies
1. **Zero PII:** All candidate real names, contact details, emails, phone numbers, and profile URLs have been completely removed.
2. **Stable Anonymization Mapping:**
   - `Candidate_A`: Computer Science & Backend Software Engineering test profile.
   - `Candidate_B`: Biomedical & Bioinformatics test profile.
3. **Mathematical Fidelity:** All numeric scores, ranking positions, Wilcoxon signed-rank statistics, and TreeSHAP values are preserved identically from original Phase B verification runs without any recalculation.

## Preserved Files Inventory
- `counterfactual_results_anonymized.csv`: Counterfactual skill-intervention evaluation results ($N=20$ random draws per job, base vs. intervened hybrid ranks, rank-gain distributions, and Wilcoxon inputs).
- `production_parity_report_anonymized.json`: Production API vs. frozen snapshot ranker parity verification results and overlap counts.
- `baseline_top10_current_anonymized.json`: Baseline top-10 rankings across BM25, SBERT, Skill Overlap, and Hybrid rankers.
- `duplicate_audit_20_clusters.json`: Job posting deduplication verification across 20 sample clusters (purely job metadata, zero PII).
- `provider_comparison_checkpoint.json`: LLM provider execution timing and latency metrics (zero PII).
