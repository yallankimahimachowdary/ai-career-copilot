"""
tests/test_evaluation_metrics.py
--------------------------------
Comprehensive unit tests for Information Retrieval metrics, Inter-Annotator Agreement,
statistical tests, annotation workflows, and ablation studies.
"""

import math
import numpy as np
import pytest

from app.ranking.evaluation import (
    cohen_kappa,
    confidence_interval,
    dcg_at_k,
    export_annotation_template,
    fleiss_kappa,
    generate_evaluation_report,
    import_relevance_judgments,
    mean_reciprocal_rank,
    ndcg_at_5,
    ndcg_at_10,
    ndcg_at_k,
    precision_at_5,
    precision_at_k,
    reciprocal_rank,
    run_ablation_study,
    wilcoxon_signed_rank_test,
)


# ==============================================================================
# 1. nDCG Calculations and Edge Cases
# ==============================================================================

def test_ndcg_perfect_ranking():
    """When items are ranked in perfect relevance order, nDCG must be 1.0."""
    ranked = ["doc_a", "doc_b", "doc_c", "doc_d"]
    judgments = {"doc_a": 3, "doc_b": 2, "doc_c": 1, "doc_d": 0}

    score_standard = ndcg_at_k(ranked, judgments, k=4, method="standard")
    assert math.isclose(score_standard, 1.0, abs_tol=1e-5)

    score_linear = ndcg_at_k(ranked, judgments, k=4, method="linear")
    assert math.isclose(score_linear, 1.0, abs_tol=1e-5)


def test_ndcg_inverted_ranking():
    """Inverted ranking must yield strictly lower nDCG than ideal."""
    ideal_ranked = ["doc_a", "doc_b"]
    inverted_ranked = ["doc_b", "doc_a"]
    judgments = {"doc_a": 3, "doc_b": 1}

    ndcg_ideal = ndcg_at_k(ideal_ranked, judgments, k=2)
    ndcg_inverted = ndcg_at_k(inverted_ranked, judgments, k=2)

    assert ndcg_ideal == 1.0
    assert 0.0 < ndcg_inverted < 1.0


def test_ndcg_manual_calculation():
    """Verify nDCG matches explicit manual logarithmic discount calculation."""
    ranked = ["doc_1", "doc_2", "doc_3"]
    judgments = {"doc_1": 2, "doc_2": 0, "doc_3": 1}

    # Standard formula: (2^rel - 1) / log2(rank + 1)
    # rank 1: (2^2 - 1) / log2(2) = 3 / 1.0 = 3.0
    # rank 2: (2^0 - 1) / log2(3) = 0 / 1.58496 = 0.0
    # rank 3: (2^1 - 1) / log2(4) = 1 / 2.0 = 0.5
    # Actual DCG@3 = 3.5
    # Ideal ranking: [doc_1 (rel 2), doc_3 (rel 1), doc_2 (rel 0)]
    # Ideal DCG@3 = 3.0 + 1 / log2(3) = 3.0 + 0.63093 = 3.63093
    # Expected nDCG@3 = 3.5 / 3.63093 ≈ 0.9639
    expected_ndcg = 3.5 / (3.0 + 1.0 / math.log2(3))

    actual_ndcg = ndcg_at_k(ranked, judgments, k=3, method="standard")
    assert math.isclose(actual_ndcg, expected_ndcg, rel_tol=1e-4)


def test_ndcg_helpers_at_5_and_10():
    """Test ndcg_at_5 and ndcg_at_10 convenience functions."""
    ranked = [f"job_{i}" for i in range(15)]
    judgments = {f"job_{i}": 10 - i for i in range(15)}

    val_5 = ndcg_at_5(ranked, judgments)
    val_10 = ndcg_at_10(ranked, judgments)
    assert val_5 == 1.0
    assert val_10 == 1.0


def test_ndcg_edge_cases():
    """Empty lists, all-zero relevance, and missing items must return 0.0."""
    assert ndcg_at_k([], {"job_1": 2}, k=5) == 0.0
    assert ndcg_at_k(["job_1"], {}, k=5) == 0.0
    assert ndcg_at_k(["job_1", "job_2"], {"job_1": 0, "job_2": 0}, k=5) == 0.0
    assert ndcg_at_k(["unjudged_a"], {"other_doc": 3}, k=5) == 0.0
    assert ndcg_at_k(["job_1"], {"job_1": 2}, k=0) == 0.0


# ==============================================================================
# 2. Precision@K and MRR
# ==============================================================================

def test_precision_at_5():
    """Verify Precision@5 with binary and graded relevance."""
    ranked = ["j1", "j2", "j3", "j4", "j5", "j6"]
    # 3 out of 5 relevant (j1, j3, j4)
    judgments = {"j1": 1, "j2": 0, "j3": 2, "j4": 1, "j5": 0, "j6": 1}

    p5 = precision_at_5(ranked, judgments, relevance_threshold=1.0)
    assert p5 == 3 / 5  # 0.60


def test_precision_at_k_edge_cases():
    """Verify Precision@k handles empty input, zero matches, and missing keys."""
    assert precision_at_k([], {"j1": 1}, k=5) == 0.0
    assert precision_at_k(["j1", "j2"], {}, k=5) == 0.0
    assert precision_at_k(["j1", "j2"], {"j1": 0, "j2": 0}, k=2, relevance_threshold=1.0) == 0.0


def test_reciprocal_rank():
    """Verify reciprocal rank identifies the first relevant item."""
    # First relevant at rank 1 -> RR = 1.0
    assert reciprocal_rank(["j1", "j2"], {"j1": 1, "j2": 0}) == 1.0

    # First relevant at rank 2 -> RR = 0.5
    assert reciprocal_rank(["j1", "j2"], {"j1": 0, "j2": 2}) == 0.5

    # First relevant at rank 4 -> RR = 0.25
    assert reciprocal_rank(["j1", "j2", "j3", "j4"], {"j4": 1}) == 0.25

    # No relevant item -> RR = 0.0
    assert reciprocal_rank(["j1", "j2"], {"j1": 0, "j2": 0}) == 0.0
    assert reciprocal_rank([], {}) == 0.0


def test_mean_reciprocal_rank():
    """Verify MRR averages across multiple queries."""
    query_rankings = [
        (["a", "b"], {"a": 1}),        # RR = 1.0
        (["a", "b"], {"b": 1}),        # RR = 0.5
        (["a", "b", "c"], {"c": 1}),  # RR = 1/3 ≈ 0.3333
        (["a", "b"], {"other": 1}),    # RR = 0.0
    ]
    expected_mrr = (1.0 + 0.5 + (1.0 / 3.0) + 0.0) / 4.0
    actual_mrr = mean_reciprocal_rank(query_rankings)
    assert math.isclose(actual_mrr, expected_mrr, rel_tol=1e-5)


# ==============================================================================
# 3. Inter-Annotator Agreement: Cohen's Kappa & Fleiss' Kappa
# ==============================================================================

def test_cohen_kappa_perfect_agreement():
    """Two identical sets of annotations must yield kappa = 1.0."""
    r1 = [1, 0, 2, 1, 0, 2, 1]
    r2 = [1, 0, 2, 1, 0, 2, 1]
    assert cohen_kappa(r1, r2) == 1.0


def test_cohen_kappa_known_values():
    """Verify Cohen's kappa on known benchmark confusion distribution."""
    # Annotator 1: 5 Yes, 5 No
    # Annotator 2: agrees on 4 Yes, agrees on 4 No, 2 disagreements
    # Total = 10, Po = 8/10 = 0.8
    # Pe = (5/10)*(5/10) + (5/10)*(5/10) = 0.25 + 0.25 = 0.50
    # Kappa = (0.8 - 0.5) / (1 - 0.5) = 0.3 / 0.5 = 0.60
    ann1 = ["Yes"] * 5 + ["No"] * 5
    ann2 = ["Yes"] * 4 + ["No"] + ["Yes"] + ["No"] * 4

    kappa = cohen_kappa(ann1, ann2)
    assert math.isclose(kappa, 0.60, abs_tol=1e-4)


def test_cohen_kappa_mismatched_lengths():
    """Mismatched rating lengths must raise ValueError."""
    with pytest.raises(ValueError, match="Annotator rating lengths must match"):
        cohen_kappa([1, 0], [1])


def test_fleiss_kappa_perfect_agreement():
    """When all raters select the same category for each subject, Fleiss' kappa must be 1.0."""
    # 5 subjects, 3 raters, 2 categories
    # Each row: 3 raters in cat 0 or 3 raters in cat 1
    matrix = [
        [3, 0],
        [3, 0],
        [0, 3],
        [3, 0],
        [0, 3],
    ]
    assert math.isclose(fleiss_kappa(matrix), 1.0, abs_tol=1e-4)


def test_fleiss_kappa_known_handbook_example():
    """Verify Fleiss' kappa against standard diagnostic agreement benchmark."""
    # 10 subjects rated by 3 raters into 3 categories
    matrix = [
        [3, 0, 0],
        [2, 1, 0],
        [0, 3, 0],
        [0, 0, 3],
        [1, 1, 1],
        [2, 0, 1],
        [0, 2, 1],
        [3, 0, 0],
        [0, 3, 0],
        [0, 0, 3],
    ]
    kappa = fleiss_kappa(matrix)
    assert 0.40 < kappa < 0.70  # Substantial/moderate agreement


def test_fleiss_kappa_invalid_inputs():
    """Invalid matrix shapes or varying rater counts must raise ValueError."""
    with pytest.raises(ValueError, match="Ratings matrix must be 2D"):
        fleiss_kappa([1, 2, 3])

    with pytest.raises(ValueError, match="at least 2 raters"):
        fleiss_kappa([[1, 0], [0, 1]])

    with pytest.raises(ValueError, match="same number of ratings"):
        fleiss_kappa([[2, 0], [3, 0]])


# ==============================================================================
# 4. Statistical Testing & Confidence Intervals
# ==============================================================================

def test_wilcoxon_signed_rank_test_identical_scores():
    """When method A and method B produce identical results, p_value must be 1.0."""
    scores_a = [0.8, 0.75, 0.9, 0.85, 0.7]
    scores_b = [0.8, 0.75, 0.9, 0.85, 0.7]

    res = wilcoxon_signed_rank_test(scores_a, scores_b)
    assert res["p_value"] == 1.0
    assert res["statistic"] == 0.0
    assert not res["significant_0_05"]


def test_wilcoxon_signed_rank_test_small_sample_size():
    """Sample sizes under 5 must be safely flagged without fabricating significance."""
    res = wilcoxon_signed_rank_test([0.9, 0.8], [0.5, 0.4])
    assert res["insufficient_sample"] is True
    assert res["p_value"] is None
    assert not res["significant_0_05"]


def test_wilcoxon_signed_rank_test_significant_difference():
    """Distinct distributions with n>=5 must compute valid test statistic and p-value."""
    scores_a = [0.95, 0.92, 0.89, 0.94, 0.91, 0.93, 0.96]
    scores_b = [0.45, 0.48, 0.50, 0.42, 0.49, 0.47, 0.44]

    res = wilcoxon_signed_rank_test(scores_a, scores_b)
    assert res["insufficient_sample"] is False
    assert res["p_value"] is not None
    assert res["p_value"] < 0.05
    assert res["significant_0_05"] is True


def test_confidence_interval_calculations():
    """Verify parametric and bootstrap confidence intervals."""
    scores = [0.80, 0.82, 0.85, 0.83, 0.84, 0.81]

    ci_t = confidence_interval(scores, confidence=0.95, method="t")
    assert ci_t["lower_bound"] < ci_t["mean"] < ci_t["upper_bound"]

    ci_boot = confidence_interval(scores, confidence=0.95, method="bootstrap", seed=42)
    assert ci_boot["lower_bound"] < ci_boot["mean"] < ci_boot["upper_bound"]

    # Constant scores edge case
    ci_const = confidence_interval([0.75, 0.75, 0.75])
    assert ci_const["lower_bound"] == ci_const["mean"] == ci_const["upper_bound"] == 0.75


# ==============================================================================
# 5. Annotation Workflows & Ablation Runs
# ==============================================================================

def test_annotation_template_export_and_import(tmp_path):
    """Verify export of annotation template and subsequent import of completed judgments."""
    candidate_results = [
        {"candidate_id": "cand_1", "candidate_name": "Mahi", "ranked_job_ids": ["job_101", "job_102"]},
        {"candidate_id": "cand_2", "candidate_name": "Deepika", "ranked_job_ids": ["job_201"]},
    ]
    snapshot_records = [
        {"id": "job_101", "title": "AI Engineer", "company_name": "Tech Corp", "location": "Remote"},
        {"id": "job_102", "title": "Data Scientist", "company_name": "Data Inc", "location": "Bengaluru"},
        {"id": "job_201", "title": "Bioinformatics Lead", "company_name": "Bio Labs", "location": "Hyderabad"},
    ]

    csv_path = tmp_path / "test_template.csv"
    export_annotation_template(candidate_results, snapshot_records, csv_path, k=5, format="csv")
    assert csv_path.exists()

    # Simulate human annotator filling in relevance grades
    content = csv_path.read_text(encoding="utf-8")
    annotated = content.replace("job_101,AI Engineer,Tech Corp,Remote,", "job_101,AI Engineer,Tech Corp,Remote,2")
    annotated = annotated.replace("job_102,Data Scientist,Data Inc,Bengaluru,", "job_102,Data Scientist,Data Inc,Bengaluru,1")
    annotated = annotated.replace("job_201,Bioinformatics Lead,Bio Labs,Hyderabad,", "job_201,Bioinformatics Lead,Bio Labs,Hyderabad,2")
    csv_path.write_text(annotated, encoding="utf-8")

    # Import judgments
    judgments = import_relevance_judgments(csv_path)
    assert "cand_1" in judgments
    assert judgments["cand_1"]["job_101"] == 2.0
    assert judgments["cand_1"]["job_102"] == 1.0
    assert judgments["cand_2"]["job_201"] == 2.0


def test_ablation_study_execution():
    """Verify ablation study runs all component variants and calculates Jaccard overlaps."""
    candidate = {
        "candidate_id": "cand_test",
        "raw_text": "Experienced Python and FastAPI backend developer with Docker experience.",
        "skills": ["python", "fastapi", "docker"],
        "summary": "Backend engineer",
    }
    snapshot_jobs = [
        {"id": "j1", "title": "Python Developer", "skills": ["python", "fastapi"]},
        {"id": "j2", "title": "Docker Systems Engineer", "skills": ["docker", "linux"]},
        {"id": "j3", "title": "Java Architect", "skills": ["java", "spring"]},
    ]

    ablations = run_ablation_study(candidate, snapshot_jobs, k=3)
    assert "full_hybrid" in ablations
    assert "ablation_no_skill_overlap" in ablations
    assert "ablation_bm25_only" in ablations
    assert "ablation_sbert_only" in ablations
    assert "ablation_overlap_only" in ablations

    assert ablations["full_hybrid"]["jaccard_similarity_to_full"] == 1.0
    assert "ranked_job_ids" in ablations["ablation_no_skill_overlap"]


def test_evaluation_report_provenance(tmp_path):
    """Verify machine-readable report contains dataset SHA-256 hash, method, seed, and timestamps."""
    dummy_snapshot = tmp_path / "snapshot.json"
    dummy_snapshot.write_text('{"jobs": []}', encoding="utf-8")

    report = generate_evaluation_report(
        dataset_path=dummy_snapshot,
        method_name="hybrid",
        seed=42,
        metrics={"ndcg@5": 0.85, "precision@5": 0.80},
    )

    assert "sha256_hash" in report["dataset"]
    assert len(report["dataset"]["sha256_hash"]) == 64
    assert report["seed"] == 42
    assert report["method"] == "hybrid"
    assert "timestamp" in report
    assert report["metrics"]["ndcg@5"] == 0.85
