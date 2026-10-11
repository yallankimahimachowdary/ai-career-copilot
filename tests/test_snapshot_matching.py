"""Reproducibility test for Frozen Snapshot Matching Pipeline."""

import pytest
from pathlib import Path
from scripts.job_snapshot import load_snapshot, run_matching_on_snapshot


def test_snapshot_matching_reproducibility():
    """Verify that loading a snapshot and matching twice produces identical rankings and scores."""
    snapshot_path = Path("data/snapshots/test_snap_1.json")
    if not snapshot_path.exists():
        pytest.skip("Snapshot file not found.")

    records, meta = load_snapshot(snapshot_path)
    assert len(records) > 0

    # Sample parsed resume representation (e.g. software engineer profile)
    sample_resume = {
        "skills": ["Python", "FastAPI", "Docker", "SQL", "Machine Learning"],
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "start_date": "2021",
                "end_date": "2024",
                "is_current": False,
            }
        ],
        "education": [
            {
                "degree": "B.Tech",
                "field_of_study": "Computer Science",
                "institution": "University",
            }
        ],
        "projects": [
            {
                "name": "Career Copilot",
                "technologies": ["Python", "FastAPI", "Docker"],
            }
        ],
    }

    # Deterministic dummy 384-dimension embedding
    sample_embedding = [0.05] * 384

    # Run matching pass 1
    run1 = run_matching_on_snapshot(
        snapshot_records=records[:50],  # test on first 50 records
        resume_parsed_data=sample_resume,
        resume_embedding=sample_embedding,
        top_k=5,
    )

    # Run matching pass 2
    run2 = run_matching_on_snapshot(
        snapshot_records=records[:50],
        resume_parsed_data=sample_resume,
        resume_embedding=sample_embedding,
        top_k=5,
    )

    assert len(run1) == 5
    assert len(run2) == 5

    # Check identical ordering and scores across both runs
    for i in range(len(run1)):
        assert run1[i]["job_id"] == run2[i]["job_id"]
        assert run1[i]["final_score"] == run2[i]["final_score"]
        assert run1[i]["composite_score"] == run2[i]["composite_score"]
        assert run1[i]["title"] == run2[i]["title"]
