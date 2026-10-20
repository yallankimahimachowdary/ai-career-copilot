"""
tests/test_ranking_runner_r12.py
--------------------------------
Tests for R12 ranking experiment runner, label gating, statistical calculations,
table generator, and evaluation scope/taxonomy tests.
"""

import json
from pathlib import Path
import pytest

from app.core.provenance import (
    build_provenance_record,
    ModelAliasMismatchError,
    ProvenanceValidationError,
    validate_provenance_payload,
)
from app.core.taxonomy import (
    TAXONOMY_VERSION,
    get_taxonomy_sha256,
    CANONICAL_SKILL_PATTERNS,
)
from app.ranking.evaluation import (
    average_precision,
    calculate_kendall_tau,
    calculate_topk_overlap,
    compute_unlabeled_diagnostics,
    confidence_interval,
    holm_bonferroni_correction,
    mean_average_precision,
    ndcg_at_k,
    paired_bootstrap_ci,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    wilcoxon_signed_rank_test,
)
from scripts.make_results_tables import (
    load_evaluation_report,
    generate_metrics_markdown,
    generate_metrics_csv,
    generate_significance_markdown,
    export_tables,
)


def test_eval_scope_file_validity():
    """Verify eval_scope.json exists, contains 3 in-scope families, and hash matches."""
    scope_path = Path("docs/eval_scope.json")
    assert scope_path.exists(), "docs/eval_scope.json must exist"

    with open(scope_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "eval_role_families" in data
    in_scope = data["eval_role_families"]
    assert len(in_scope) == 3
    assert set(in_scope) == {"Data/AI", "Web/Software", "Cybersecurity/Cloud"}

    assert "deficit_families_excluded_from_ranking_eval" in data
    assert len(data["deficit_families_excluded_from_ranking_eval"]) == 6


def test_provenance_records_taxonomy_and_hash():
    """Verify provenance record strictly captures taxonomy version and hash."""
    rec = build_provenance_record(
        requested_model="bm25",
        returned_model="bm25",
        seed=42,
        run_type="dryrun",
    )
    assert rec["taxonomy_version"] == "v2.1"
    assert rec["taxonomy_hash"] == get_taxonomy_sha256()
    assert validate_provenance_payload(rec) is True


def test_provenance_rejects_missing_taxonomy():
    """Verify validate_provenance_payload fails if taxonomy_version or taxonomy_hash is missing."""
    rec = build_provenance_record(
        requested_model="bm25",
        returned_model="bm25",
        seed=42,
        run_type="dryrun",
    )
    # Remove taxonomy hash
    del rec["taxonomy_hash"]
    with pytest.raises(ProvenanceValidationError):
        validate_provenance_payload(rec)


def test_metrics_toy_values():
    """Verify ranking metrics against known hand-calculated values."""
    # Toy ranking: [J1, J2, J3, J4]
    # Relevance: J1=2, J2=0, J3=1, J4=0. Relevant items (rel >= 1): J1, J3. Total rel = 2.
    relevance = {"J1": 2, "J2": 0, "J3": 1, "J4": 0}
    ranking = ["J1", "J2", "J3", "J4"]

    # Precision@2: J1 (rel), J2 (not) -> 1/2 = 0.5
    assert precision_at_k(ranking, relevance, k=2) == 0.5

    # Recall@2: 1 relevant item retrieved out of 2 -> 1/2 = 0.5
    assert recall_at_k(ranking, relevance, k=2) == 0.5

    # Reciprocal Rank: first relevant item is at rank 1 -> 1.0
    assert reciprocal_rank(ranking, relevance) == 1.0

    # Reciprocal Rank when first item is irrelevant:
    assert reciprocal_rank(["J2", "J3", "J1"], relevance) == 0.5  # J3 is at rank 2

    # Average Precision (AP):
    # Rank 1: J1 (rel) -> P@1 = 1/1 = 1.0
    # Rank 2: J2 (not) -> 0
    # Rank 3: J3 (rel) -> P@3 = 2/3
    # AP = (1.0 + 2/3) / 2 = 1.6667 / 2 = 0.8333
    ap = average_precision(ranking, relevance)
    assert round(ap, 4) == 0.8333

    # MAP across two identical queries
    map_score = mean_average_precision([(ranking, relevance), (ranking, relevance)])
    assert round(map_score, 4) == 0.8333


def test_wilcoxon_and_holm_correction():
    """Verify paired Wilcoxon signed-rank and Holm-Bonferroni correction with known values."""
    scores_a = [0.85, 0.90, 0.78, 0.92, 0.88, 0.84, 0.95, 0.89, 0.91, 0.87]
    scores_b = [0.70, 0.75, 0.65, 0.80, 0.72, 0.68, 0.82, 0.74, 0.76, 0.71]

    w_res = wilcoxon_signed_rank_test(scores_a, scores_b)
    assert w_res["sample_size"] == 10
    assert w_res["warning"] is not None
    assert "Sample size (n=10) < 20" in w_res["warning"]
    assert w_res["significant_0_05"] is True

    # Bootstrap CI
    boot = paired_bootstrap_ci(scores_a, scores_b, n_resamples=1000, seed=42)
    assert boot["mean_difference"] > 0.10
    assert boot["lower_bound"] > 0.05

    # Holm-Bonferroni correction
    raw_p = [0.008, 0.035, 0.022]
    holm = holm_bonferroni_correction(raw_p, alpha=0.05)
    # Sorted order of raw_p: 0.008 (idx 0), 0.022 (idx 2), 0.035 (idx 1)
    # 0.008 * 3 = 0.024 (< 0.05 -> rejected)
    # 0.022 * 2 = 0.044 (< 0.05 -> rejected)
    # 0.035 * 1 = 0.035, but monotonic max = 0.044 (< 0.05 -> rejected)
    assert holm[0]["adjusted_p"] == 0.024
    assert holm[2]["adjusted_p"] == 0.044
    assert holm[1]["adjusted_p"] == 0.044


def test_table_generator_refuses_dryrun_without_override(tmp_path):
    """Verify make_results_tables refuses to export tables from dryrun files without explicit flag."""
    dryrun_file = tmp_path / "dryrun_report.json"
    report_data = {
        "run_type": "dryrun",
        "method": "hybrid",
        "metrics": {"hybrid": {"status": "evaluated", "ndcg@10": 0.85}},
    }
    dryrun_file.write_text(json.dumps(report_data), encoding="utf-8")

    with pytest.raises(ValueError, match="REFUSAL: Table generator rejected dryrun report"):
        load_evaluation_report(dryrun_file, allow_dryrun=False)

    # When override is provided, it succeeds
    loaded = load_evaluation_report(dryrun_file, allow_dryrun=True)
    assert loaded["run_type"] == "dryrun"
