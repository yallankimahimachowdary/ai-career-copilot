"""Tests for Dataset Overlap and Contamination Checks (Prompt P1C)."""

import subprocess
import sys
import pytest

from scripts.check_dataset_overlap import (
    compute_content_hash,
    load_test_resumes,
    verify_no_overlap,
    classify_job_family,
    audit_role_family_coverage,
    audit_60_job_universe_overlap_and_leakage,
)
from scripts.tune_hybrid_weights import prepare_dev_resumes


def test_repo_dev_and_test_have_zero_overlap():
    """Verify that current repository dev benchmarks and gold test benchmark sets have 0 overlap."""
    dev_resumes = prepare_dev_resumes()
    test_resumes = load_test_resumes()

    assert len(dev_resumes) >= 2
    assert len(test_resumes) >= 2

    report = verify_no_overlap(dev_resumes, test_resumes)
    assert report["has_overlap"] is False
    assert report["overlapping_count"] == 0


def test_overlap_check_detects_contamination():
    """Verify that verify_no_overlap raises ValueError when identical content is in both splits."""
    dev_resumes = [
        {"candidate_name": "Dev_Candidate_A", "text": "Senior Python Developer with FastAPI and Docker experience."},
        {"candidate_name": "Dev_Candidate_B", "text": "Bioinformatics Researcher with PCR experience."},
    ]
    test_resumes = [
        {"candidate_name": "Test_Candidate_X", "text": "Senior Python Developer with FastAPI and Docker experience."},  # Exact match
        {"candidate_name": "Test_Candidate_Y", "text": "Machine Learning Engineer with PyTorch experience."},
    ]

    with pytest.raises(ValueError, match="Dataset overlap detected"):
        verify_no_overlap(dev_resumes, test_resumes)


def test_overlap_check_detects_normalized_whitespace_contamination():
    """Verify that whitespace/case differences in duplicate resumes are caught by normalized hashing."""
    dev_resumes = [
        {"candidate_name": "Dev_1", "text": "   Senior   Python  Developer\nwith FastAPI   "},
    ]
    test_resumes = [
        {"candidate_name": "Test_1", "text": "senior python developer with fastapi"},
    ]

    with pytest.raises(ValueError, match="Dataset overlap detected"):
        verify_no_overlap(dev_resumes, test_resumes)


def test_overlap_check_passes_on_disjoint_resumes():
    """Verify clean pass for disjoint resume sets."""
    dev_resumes = [
        {"candidate_name": "Dev_1", "text": "Unique dev resume text about embedded systems and C++."},
    ]
    test_resumes = [
        {"candidate_name": "Test_1", "text": "Unique test resume text about cloud architecture and Kubernetes."},
    ]

    report = verify_no_overlap(dev_resumes, test_resumes)
    assert report["has_overlap"] is False
    assert report["overlapping_count"] == 0


def test_check_dataset_overlap_cli_exit_code():
    """Verify that running scripts/check_dataset_overlap.py directly exits with 0 on clean dataset."""
    import os
    env = dict(os.environ, PYTHONPATH=".")
    result = subprocess.run(
        [sys.executable, "scripts/check_dataset_overlap.py"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "Zero content-hash overlap confirmed" in result.stdout


def test_classify_job_family_mapping():
    assert classify_job_family("Senior Data Scientist") == "Data/AI"
    assert classify_job_family("Machine Learning Engineer") == "Data/AI"
    assert classify_job_family("Full Stack Software Developer") == "Web/Software"
    assert classify_job_family("Android Mobile App Developer") == "Mobile/UI-UX"
    assert classify_job_family("Cloud Security Architect") == "Cybersecurity/Cloud"
    assert classify_job_family("VLSI Embedded Hardware Engineer") == "Electrical"
    assert classify_job_family("Mechanical Design CAD Engineer") == "Mechanical"
    assert classify_job_family("Civil Site Engineer") == "Civil"
    assert classify_job_family("Senior Accountant / Auditor") == "Commerce/Finance"
    assert classify_job_family("Technical Content Writer") == "Arts/Media"


def test_audit_role_family_coverage():
    mock_jobs = [
        {"id": f"j_data_{i}", "title": "Data Analyst", "description": "SQL and Python"}
        for i in range(65)
    ] + [
        {"id": f"j_mech_{i}", "title": "Mechanical Engineer", "description": "CAD design"}
        for i in range(15)
    ]

    cov = audit_role_family_coverage(mock_jobs)
    assert "Data/AI" in cov["can_fill_families"]
    assert cov["breakdown"]["Data/AI"]["can_fill_60_universe"] is True
    assert cov["breakdown"]["Data/AI"]["count"] == 65

    assert "Mechanical" in cov["cannot_fill_families"]
    assert cov["breakdown"]["Mechanical"]["can_fill_60_universe"] is False
    assert cov["breakdown"]["Mechanical"]["count"] == 15
    assert cov["breakdown"]["Mechanical"]["deficit"] == 45


def test_universe_overlap_and_leakage_detection():
    jobs_pool = [
        {"id": f"job_py_{i}", "title": f"Python Developer {i}", "description": "Python, FastAPI", "skills": ["Python"]}
        for i in range(5)
    ] + [
        {"id": f"job_java_{i}", "title": f"Java Architect {i}", "description": "Java, Spring", "skills": ["Java"]}
        for i in range(5)
    ] + [
        {"id": f"job_react_{i}", "title": f"React Frontend {i}", "description": "React, JavaScript", "skills": ["React"]}
        for i in range(5)
    ] + [
        {"id": f"job_data_{i}", "title": f"Data Analyst {i}", "description": "SQL, Tableau", "skills": ["SQL"]}
        for i in range(5)
    ]

    test_resumes = [
        {"candidate_id": "test_1", "skills": ["Python"], "summary": "Python Developer"},
        {"candidate_id": "test_2", "skills": ["Python"], "summary": "Python Developer"},
    ]

    # Dev resume identical to test_1 to test leakage detection
    dev_resumes_leak = [
        {"candidate_id": "dev_leak", "skills": ["Python"], "summary": "Python Developer"}
    ]

    leak_audit = audit_60_job_universe_overlap_and_leakage(
        test_resumes=test_resumes,
        dev_resumes=dev_resumes_leak,
        jobs_pool=jobs_pool,
        universe_size=5,
    )
    assert leak_audit["leakage_detected"] is True

    # Dev resume distinct in different domain (Java Architect)
    dev_resumes_clean = [
        {"candidate_id": "dev_clean", "skills": ["Java"], "summary": "Java Architect"}
    ]
    clean_audit = audit_60_job_universe_overlap_and_leakage(
        test_resumes=test_resumes,
        dev_resumes=dev_resumes_clean,
        jobs_pool=jobs_pool,
        universe_size=5,
    )
    assert clean_audit["dev_set_leakage_checks"][0]["leakage_flag"] is False
    assert clean_audit["leakage_detected"] is False

