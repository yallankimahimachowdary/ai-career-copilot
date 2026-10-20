"""
tests/test_r13b_corrections.py
------------------------------
Unit tests for Remediation R13b verification items:
1. Universe-only ranking: evaluation rejects snapshot slice and requires candidate universes.
2. Prompt hash equality: prompt hashes remain bit-for-bit identical across repeats.
3. Claim negation: negated requirements are not validated as required missing skills.
4. Alias matching: taxonomy aliases (k8s -> Kubernetes, GCP -> Google Cloud, etc.) resolve correctly.
5. Counterfactual direction: missing required skill provides rank gain over irrelevant within-family control skill.
"""

import copy
import hashlib
import pytest
from app.ranking.claim_verifier import ClaimVerifier
from app.ranking.counterfactual import CounterfactualTester
from app.ranking.hybrid import HybridRanker
from app.ranking.llm_reranker import _format_resume_summary
from scripts.evaluate_ranking import run_evaluation_pipeline


def test_universe_only_ranking_refuses_snapshot_slice(tmp_path):
    """Enforce that real evaluation or pipeline runs with judgments strictly forbid max_jobs slicing."""
    fake_judgments = tmp_path / "labels.jsonl"
    fake_judgments.write_text('{"query_id": "SYN_001", "doc_id": "job_1", "rating": 3}\n', encoding="utf-8")

    # When judgments are provided (real or dryrun eval mode), dryrun_max_jobs_slice must raise ValueError
    with pytest.raises(ValueError, match="Slicing snapshot jobs via dryrun_max_jobs_slice"):
        run_evaluation_pipeline(
            snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
            output_report_path=str(tmp_path / "report.json"),
            judgments_path=str(fake_judgments),
            run_type="real",
            dryrun_max_jobs_slice=100,
        )


def test_prompt_hashes_identical_across_repeats():
    """Verify prompt formatting and prompt hash are completely deterministic across repeat invocations."""
    cand = {
        "candidate_id": "SYN_001",
        "candidate_name": "Aarav Sharma",
        "summary": "Data Scientist with PyTorch and NLP experience.",
        "skills": ["Python", "PyTorch", "SQL", "NLP"],
        "experience": [
            {"title": "Data Science Intern", "company": "Tech Corp", "description": "Built NLP pipelines"}
        ],
    }

    # Format summary repeatedly
    prompt_1 = _format_resume_summary(cand)
    hash_1 = hashlib.sha256(prompt_1.encode("utf-8")).hexdigest()

    prompt_2 = _format_resume_summary(cand)
    hash_2 = hashlib.sha256(prompt_2.encode("utf-8")).hexdigest()

    prompt_3 = _format_resume_summary(copy.deepcopy(cand))
    hash_3 = hashlib.sha256(prompt_3.encode("utf-8")).hexdigest()

    assert prompt_1 == prompt_2 == prompt_3
    assert hash_1 == hash_2 == hash_3


def test_claim_negation_detection():
    """Verify that negated skills in job descriptions are rejected by ClaimVerifier."""
    verifier = ClaimVerifier()
    resume = {
        "skills": ["Python", "Docker"],
        "summary": "Backend developer with Python and Docker.",
    }
    job = {
        "title": "Backend Python Developer",
        "description": "Looking for Python and Docker. Java is not required for this role. No Kubernetes needed.",
        "skills": ["Python", "Docker"],
    }

    # Explanation claims Java and Kubernetes are missing requirements
    exp = {
        "job_id": "job_test_neg",
        "rank": 1,
        "matched_skills": ["Python", "Docker"],
        "missing_skills": ["Java", "Kubernetes"],
        "reason": "Strong Python candidate, but lacks Java and Kubernetes.",
    }

    res = verifier.verify_explanation(exp, resume, job)
    # Both Java and Kubernetes were explicitly negated in the job description
    assert "Java" in res.invalid_missing
    assert "Kubernetes" in res.invalid_missing
    assert len(res.valid_missing) == 0
    assert res.faithfulness_score < 1.0


def test_claim_alias_matching():
    """Verify that canonical aliases resolve bidirectionally between resume, job, and claims."""
    verifier = ClaimVerifier()
    resume = {
        "skills": ["GCP", "Postgres", "k8s"],
        "summary": "Cloud developer experienced in GCP, Postgres, and k8s.",
    }
    job = {
        "title": "Cloud Platform Engineer",
        "description": "Requires Google Cloud Platform, PostgreSQL, and Kubernetes.",
        "skills": ["Google Cloud", "PostgreSQL", "Kubernetes"],
    }

    exp = {
        "job_id": "job_alias",
        "rank": 1,
        "matched_skills": ["Google Cloud", "Kubernetes", "PostgreSQL"],
        "missing_skills": [],
        "reason": "Candidate has strong Google Cloud, Kubernetes, and PostgreSQL experience.",
    }

    res = verifier.verify_explanation(exp, resume, job)
    assert len(res.invalid_matched) == 0
    assert "Google Cloud" in res.valid_matched
    assert "Kubernetes" in res.valid_matched
    assert "PostgreSQL" in res.valid_matched
    assert res.faithfulness_score == 1.0


def test_counterfactual_direction_rank_change():
    """Verify that adding a suggested missing skill improves or maintains target job rank vs control."""
    hybrid = HybridRanker()
    cand = {
        "candidate_id": "TEST_001",
        "skills": ["Python", "SQL"],
        "summary": "Python and SQL developer.",
        "raw_text": "Python and SQL developer looking for backend roles.",
    }

    jobs = [
        {"id": "job_1", "title": "Python Developer", "skills": ["Python", "SQL"], "description": "Python SQL"},
        {"id": "job_2", "title": "Data Engineer", "skills": ["Python", "SQL", "Spark"], "description": "Python SQL Apache Spark"},
        {"id": "job_3", "title": "Frontend Developer", "skills": ["React", "CSS"], "description": "React CSS"},
    ]

    base_rank = hybrid.rank(cand, jobs, k=3)
    old_rank_job2 = base_rank.ranked_job_ids.index("job_2") + 1

    # Condition A: Add suggested missing skill ("Spark")
    cand_sugg = copy.deepcopy(cand)
    cand_sugg["skills"].append("Spark")
    cand_sugg["raw_text"] += " Spark"
    rank_sugg = hybrid.rank(cand_sugg, jobs, k=3)
    new_rank_sugg = rank_sugg.ranked_job_ids.index("job_2") + 1
    gain_sugg = old_rank_job2 - new_rank_sugg

    # Condition B: Add unrelated control skill ("Ruby")
    cand_ctrl = copy.deepcopy(cand)
    cand_ctrl["skills"].append("Ruby")
    cand_ctrl["raw_text"] += " Ruby"
    rank_ctrl = hybrid.rank(cand_ctrl, jobs, k=3)
    new_rank_ctrl = rank_ctrl.ranked_job_ids.index("job_2") + 1
    gain_ctrl = old_rank_job2 - new_rank_ctrl

    # Suggested required skill must produce equal or better gain than unrelated control
    assert gain_sugg >= gain_ctrl
    assert rank_sugg.scores["job_2"] > base_rank.scores["job_2"]
