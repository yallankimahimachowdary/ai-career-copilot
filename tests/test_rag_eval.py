"""
tests/test_rag_eval.py
----------------------
Unit tests for the RAG and Coach Answer Grounding evaluation framework.
Verifies context recall, context precision, answer factual consistency,
hallucination detection, citation grounding, and transparent human-review handling.
"""

from pathlib import Path
import pytest

from app.services.rag_eval import (
    HumanEvaluationRecord,
    RAGBenchmarkSample,
    RetrievedChunk,
    check_factual_consistency,
    compute_context_precision,
    compute_context_recall,
    compute_token_f1,
    rag_coach_evaluator,
    verify_source_grounding,
)


@pytest.fixture
def sample_rag_record():
    return RAGBenchmarkSample(
        sample_id="TEST-001",
        category="skill_gap_analysis",
        query="What skills do I need for Senior Backend?",
        retrieved_context=[
            RetrievedChunk(
                source_id="job_reqs_senior",
                source_type="job_posting",
                content="Requirements: Kubernetes, Distributed Systems, System Design, Redis, Python.",
            ),
            RetrievedChunk(
                source_id="resume_skills",
                source_type="candidate_resume",
                content="Skills: Python, FastAPI, PostgreSQL, Docker.",
            ),
        ],
        reference_answer="You need to learn Kubernetes, Distributed Systems, System Design, and Redis. You already know Python and PostgreSQL.",
        required_key_facts=[
            "Kubernetes",
            "Distributed Systems",
            "System Design",
            "Redis",
            "Python",
        ],
        prohibited_hallucinations=[
            "must have a PhD in AI",
            "requires 20 years experience",
        ],
        human_evaluation=HumanEvaluationRecord(status="pending_review", rating=None),
    )


def test_compute_token_f1():
    """Verify precision, recall, and harmonic mean computation over word tokens."""
    ref = "The quick brown fox jumps over the lazy dog"
    pred_exact = "The quick brown fox jumps over the lazy dog"
    pred_partial = "The quick brown fox"
    pred_disjoint = "Completely different text here"

    assert compute_token_f1(pred_exact, ref) == 1.0
    assert 0.0 < compute_token_f1(pred_partial, ref) < 1.0
    assert compute_token_f1(pred_disjoint, ref) == 0.0
    assert compute_token_f1("", ref) == 0.0


def test_compute_context_recall():
    """Context recall verifies that required gold facts exist within retrieved context chunks."""
    contexts = [
        "Requirements: Kubernetes, Distributed Systems, System Design.",
        "Candidate knows Python and PostgreSQL.",
    ]
    facts = ["Kubernetes", "Distributed Systems", "Python"]
    recall, missing = compute_context_recall(facts, contexts)
    assert recall == 1.0
    assert len(missing) == 0

    # Test partial recall
    facts_with_missing = ["Kubernetes", "Distributed Systems", "Redis", "Rust"]
    recall2, missing2 = compute_context_recall(facts_with_missing, contexts)
    assert recall2 == 0.5
    assert set(missing2) == {"Redis", "Rust"}


def test_compute_context_precision():
    """Context precision evaluates signal-to-noise across retrieved chunks."""
    required = ["Kubernetes", "Python"]
    chunks = [
        "Relevant chunk containing Kubernetes instructions.",
        "Noise chunk talking about unrelated hobbies and weather.",
        "Another relevant chunk mentioning Python frameworks.",
    ]
    precision = compute_context_precision(required, chunks)
    # 2 out of 3 chunks are relevant
    assert precision == round(2 / 3, 4)


def test_check_factual_consistency_clean_answer():
    """Clean grounded answers score high without hallucination flags."""
    answer = "To transition, focus on Kubernetes, Distributed Systems, System Design, Redis, and build on Python."
    contexts = [
        "Requirements: Kubernetes, Distributed Systems, System Design, Redis, Python.",
    ]
    required = ["Kubernetes", "Distributed Systems", "System Design", "Redis", "Python"]
    prohibited = ["must have a PhD in AI"]

    score, missing, hallucinations = check_factual_consistency(
        generated_answer=answer,
        retrieved_contexts=contexts,
        required_facts=required,
        prohibited_hallucinations=prohibited,
    )

    assert score == 1.0
    assert len(missing) == 0
    assert len(hallucinations) == 0


def test_check_factual_consistency_with_hallucination():
    """Prohibited hallucinations are detected and penalize the consistency score."""
    answer = "You must have a PhD in AI to apply, and you need Kubernetes and Python."
    contexts = ["Requirements: Kubernetes and Python."]
    required = ["Kubernetes", "Python"]
    prohibited = ["must have a PhD in AI"]

    score, missing, hallucinations = check_factual_consistency(
        generated_answer=answer,
        retrieved_contexts=contexts,
        required_facts=required,
        prohibited_hallucinations=prohibited,
    )

    assert "must have a PhD in AI" in hallucinations
    assert score < 1.0  # Penalized by hallucination


def test_verify_source_grounding():
    """Citation check ensures answers cite valid retrieved chunk IDs."""
    chunks = [
        RetrievedChunk(source_id="resume_skills", source_type="candidate_resume", content="Python"),
        RetrievedChunk(source_id="job_posting_1", source_type="job_posting", content="Kubernetes"),
    ]

    valid_citations = ["resume_skills", "job_posting_1"]
    invalid_citations = ["resume_skills", "hallucinated_database_doc"]

    assert verify_source_grounding(valid_citations, chunks) is True
    assert verify_source_grounding(invalid_citations, chunks) is False


def test_human_review_separation_never_fabricates_ratings(sample_rag_record):
    """Evaluator must preserve human review state as pending/None and not invent ratings."""
    res = rag_coach_evaluator.evaluate_sample(
        sample_rag_record,
        generated_answer=sample_rag_record.reference_answer,
        citations=["job_reqs_senior", "resume_skills"],
    )

    assert res.human_evaluation_status == "pending_review"
    assert res.human_rating is None
    assert res.valid_source_grounding is True
    assert res.context_recall == 1.0


def test_evaluate_benchmark_suite_gold_dataset():
    """End-to-end evaluation on the versioned gold benchmark dataset."""
    dataset_path = Path("data/evaluation/rag_coach_eval_v1.json")
    assert dataset_path.exists(), "Benchmark dataset must exist"

    report = rag_coach_evaluator.evaluate_benchmark_suite(dataset_path)

    assert report.total_samples == 5
    assert report.mean_context_recall >= 0.95
    assert report.mean_factual_consistency >= 0.95
    assert report.hallucination_rate == 0.0
    assert report.grounding_pass_rate == 1.0
    assert report.human_review_summary["unreviewed_rating_fabricated"] is False
    assert report.human_review_summary["pending_review_count"] == 5
