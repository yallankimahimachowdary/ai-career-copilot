"""
tests/test_r14_real_run_readiness.py
------------------------------------
Tests for R14 real-run readiness, resume intake, contamination guards,
PII scrubbing, and staged pipeline execution.
"""

import json
from pathlib import Path
import pytest

from app.core.taxonomy import TAXONOMY_VERSION, get_taxonomy_sha256
from scripts.intake_resumes import (
    process_resume_intake,
    detect_synthetic_contamination,
    verify_zero_pii_in_text,
    ResumeContaminationError,
)
from scripts.run_all import (
    verify_frozen_hashes,
    run_secret_scanner,
    check_services_health,
)


def test_frozen_hashes_pass_without_modification():
    """Verify that verify_frozen_hashes succeeds on the pristine repository."""
    assert verify_frozen_hashes() is True


def test_synthetic_contamination_detection(tmp_path):
    """Verify that detect_synthetic_contamination correctly identifies synthetic files."""
    # Synthetic name
    pdf_syn_name = tmp_path / "SYN_001_Test.pdf"
    assert detect_synthetic_contamination(pdf_syn_name, "Some generic resume text") is True

    # Real name with synthetic footer
    pdf_real_name = tmp_path / "John_Doe.pdf"
    text_with_footer = "Experience in Python and SQL.\nSynthetic test resume - fictional person, not real data"
    assert detect_synthetic_contamination(pdf_real_name, text_with_footer) is True

    # Real name without synthetic footer
    clean_text = "Experience in Python, FastAPI, and PostgreSQL."
    assert detect_synthetic_contamination(pdf_real_name, clean_text) is False


def test_zero_pii_verification():
    """Verify that verify_zero_pii_in_text detects unmasked email and phone numbers."""
    text_with_pii = "Contact me at candidate@example.com or +91 9876543210 for inquiries."
    is_clean, leaks = verify_zero_pii_in_text(text_with_pii)
    assert is_clean is False
    assert len(leaks) >= 2

    clean_text = "Experienced Senior Python Engineer with skills in FastAPI, Docker, and PostgreSQL."
    is_clean2, leaks2 = verify_zero_pii_in_text(clean_text)
    assert is_clean2 is True
    assert len(leaks2) == 0


def test_intake_refuses_synthetic_in_real_mode(tmp_path):
    """Verify that process_resume_intake raises ResumeContaminationError if synthetic resumes are passed with run_type=real."""
    # We test with existing synthetic resume folder
    with pytest.raises(ResumeContaminationError, match="CONTAMINATION ERROR: Synthetic resumes detected"):
        process_resume_intake(
            resumes_dir="data/resumes_dryrun",
            output_dir=tmp_path / "real_out",
            run_type="real",
            allow_synthetic=False,
        )


def test_intake_dryrun_mode_succeeds(tmp_path):
    """Verify that process_resume_intake with run_type=dryrun and allow_synthetic=True succeeds."""
    report = process_resume_intake(
        resumes_dir="data/resumes_dryrun",
        output_dir=tmp_path / "dryrun_out",
        run_type="dryrun",
        allow_synthetic=True,
    )
    assert report["counts"]["total_files_inspected"] == 95
    assert report["counts"]["successfully_parsed"] == 95
    assert report["zero_pii_audit"]["all_resumes_pii_clean"] is True
    assert report["metadata"]["run_type"] == "dryrun"


def test_planted_fixture_pii_anonymization(tmp_path):
    """Verify zero-PII audit on a planted resume containing name, email, phone number."""
    from app.services.anonymizer import anonymize_resume
    
    raw_planted_resume = (
        "Candidate Name: Rajesh Sharma\n"
        "Email: rajesh.sharma.engineer@gmail.com\n"
        "Phone: +91 9876543210\n"
        "Education: Bachelor of Technology from International Institute of Information Technology (IIIT)\n"
        "Experience: 5 years in Python, FastAPI, Docker, and PostgreSQL.\n"
    )
    
    anonymized = anonymize_resume(raw_planted_resume, candidate_name="Rajesh Sharma", strip_institutions=True)
    is_clean, leaks = verify_zero_pii_in_text(anonymized)
    assert is_clean is True, f"Found PII leaks: {leaks}"
    assert "rajesh.sharma.engineer@gmail.com" not in anonymized
    assert "+91 9876543210" not in anonymized
    assert "9876543210" not in anonymized


def test_eval_stage_requires_labels_file(tmp_path):
    """Verify that stage eval refuses to run without a valid labels file."""
    from scripts.run_all import run_stage_eval

    with pytest.raises(FileNotFoundError, match="Stage EVAL requires human annotations"):
        run_stage_eval(
            labels_path=str(tmp_path / "nonexistent_labels.jsonl"),
            snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
            resumes_dir="data/resumes_dryrun",
            run_type="real",
        )


def test_stage_manifest_dryrun_structure():
    """Verify that stage_all_dryrun_manifest.json contains required provenance keys."""
    manifest_path = Path("results/dryrun/stage_all_dryrun_manifest.json")
    assert manifest_path.exists(), "stage_all_dryrun_manifest.json must exist"
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["stage"] == "all-dryrun"
    assert data["run_type"] == "dryrun"
    assert data["taxonomy_version"] == TAXONOMY_VERSION
    assert data["taxonomy_hash"] == get_taxonomy_sha256()
    assert "git_commit" in data
    assert "config_hash" in data
    assert data["status"] == "all_dryrun_complete"
    assert "eval_report_hash" in data
    assert "tables" in data

