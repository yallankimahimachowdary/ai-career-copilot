"""Tests for Dataset Overlap and Contamination Checks (Prompt P1C)."""

import subprocess
import sys
import pytest

from scripts.check_dataset_overlap import compute_content_hash, load_test_resumes, verify_no_overlap
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
    assert "Zero dataset overlap confirmed" in result.stdout
