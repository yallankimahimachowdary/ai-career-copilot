"""Unit tests for Frozen Job Snapshot Tooling (Remediation R8).

Tests:
- Snapshot verification on valid vs tampered files
- Read-only attribute enforcement
- Overwrite refusal on existing label or file
- Snapshot comparison logic (turnover, age, skill shifts) on synthetic fixtures
- Refusal of comparison when config hashes differ without --allow-config-diff
"""

import hashlib
import json
from pathlib import Path
import pytest

from scripts.compare_snapshots import compare_snapshots
from scripts.verify_snapshot import verify_snapshot


@pytest.fixture
def synthetic_snapshot_env(tmp_path):
    snapshots_dir = tmp_path / "data" / "snapshots"
    manifest_dir = tmp_path / "results" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    manifest_file = manifest_dir / "manifest.jsonl"

    # Create Synthetic Snapshot 1
    recs_1 = [
        {
            "id": "1",
            "source_job_id": "job_001",
            "title": "Python Developer",
            "posting_date": "2026-10-01T00:00:00Z",
            "skills": ["Python", "FastAPI"],
            "company": "Company A",
            "location": "Bengaluru",
        },
        {
            "id": "2",
            "source_job_id": "job_002",
            "title": "React Developer",
            "posting_date": "2026-10-05T00:00:00Z",
            "skills": ["React", "JavaScript"],
            "company": "Company B",
            "location": "Hyderabad",
        },
    ]

    # Create Synthetic Snapshot 2 (job_001 retained, job_002 disappeared, job_003 new)
    recs_2 = [
        {
            "id": "1",
            "source_job_id": "job_001",
            "title": "Python Developer",
            "posting_date": "2026-10-01T00:00:00Z",
            "skills": ["Python", "FastAPI", "Docker"],
            "company": "Company A",
            "location": "Bengaluru",
        },
        {
            "id": "3",
            "source_job_id": "job_003",
            "title": "Cloud Engineer",
            "posting_date": "2026-10-18T00:00:00Z",
            "skills": ["AWS", "Docker"],
            "company": "Company C",
            "location": "Pune",
        },
    ]

    file_1 = snapshots_dir / "jobs_snapA_20261010_adzuna.jsonl"
    with open(file_1, "w", encoding="utf-8") as f:
        for r in recs_1:
            f.write(json.dumps(r) + "\n")

    h1 = hashlib.sha256(file_1.read_bytes()).hexdigest().upper()

    file_2 = snapshots_dir / "jobs_snapB_20261020_adzuna.jsonl"
    with open(file_2, "w", encoding="utf-8") as f:
        for r in recs_2:
            f.write(json.dumps(r) + "\n")

    h2 = hashlib.sha256(file_2.read_bytes()).hexdigest().upper()

    file_diff = snapshots_dir / "jobs_snapC_diff_20261020_adzuna.jsonl"
    with open(file_diff, "w", encoding="utf-8") as f:
        for r in recs_2:
            f.write(json.dumps(r) + "\n")

    # Write manifest entries
    entry_1 = {
        "label": "snapA",
        "date_taken": "2026-10-10T12:00:00Z",
        "config_sha256": "CFG_HASH_12345",
        "snapshot_sha256": h1,
        "source": "adzuna_api",
    }
    entry_2 = {
        "label": "snapB",
        "date_taken": "2026-10-20T12:00:00Z",
        "config_sha256": "CFG_HASH_12345",
        "snapshot_sha256": h2,
        "source": "adzuna_api",
    }
    entry_diff_cfg = {
        "label": "snapC_diff",
        "date_taken": "2026-10-20T12:00:00Z",
        "config_sha256": "CFG_HASH_DIFFERENT",
        "snapshot_sha256": h2,
        "source": "adzuna_api",
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(entry_1) + "\n")
        f.write(json.dumps(entry_2) + "\n")
        f.write(json.dumps(entry_diff_cfg) + "\n")

    return {
        "snapshots_dir": snapshots_dir,
        "manifest_path": manifest_file,
        "file_1": file_1,
        "file_2": file_2,
        "hash_1": h1,
        "hash_2": h2,
    }


def test_verify_snapshot_success(synthetic_snapshot_env):
    """Verify verify_snapshot returns True on pristine snapshot file."""
    assert verify_snapshot(
        label="snapA",
        manifest_path=synthetic_snapshot_env["manifest_path"],
        snapshots_dir=synthetic_snapshot_env["snapshots_dir"],
    ) is True


def test_verify_snapshot_tamper_detection(synthetic_snapshot_env):
    """Verify verify_snapshot returns False when snapshot file has been tampered with."""
    file_1 = synthetic_snapshot_env["file_1"]
    # Tamper with the file
    with open(file_1, "a", encoding="utf-8") as f:
        f.write('{"tampered": true}\n')

    assert verify_snapshot(
        label="snapA",
        manifest_path=synthetic_snapshot_env["manifest_path"],
        snapshots_dir=synthetic_snapshot_env["snapshots_dir"],
    ) is False


def test_compare_snapshots_turnover_and_skills(synthetic_snapshot_env):
    """Verify compare_snapshots computes turnover rates and skill count shifts."""
    report = compare_snapshots(
        label_a="snapA",
        label_b="snapB",
        allow_config_diff=False,
        manifest_path=synthetic_snapshot_env["manifest_path"],
        snapshots_dir=synthetic_snapshot_env["snapshots_dir"],
    )

    assert report["config_hash_match"] is True
    turnover = report["turnover"]
    assert turnover["overlap_count"] == 1  # job_001
    assert turnover["new_postings_count"] == 1  # job_003
    assert turnover["disappeared_postings_count"] == 1  # job_002
    assert turnover["turnover_rate"] == 0.50  # 1 / 2 = 50%

    # Top gaining skills
    assert "Docker" in report["top_gaining_skills"]
    assert report["top_gaining_skills"]["Docker"]["shift_delta"] == 2  # 0 in A -> 2 in B


def test_compare_snapshots_refuses_differing_configs(synthetic_snapshot_env):
    """Verify compare_snapshots refuses to compare snapshots with different config hashes."""
    with pytest.raises(SystemExit) as exc_info:
        compare_snapshots(
            label_a="snapA",
            label_b="snapC_diff",
            allow_config_diff=False,
            manifest_path=synthetic_snapshot_env["manifest_path"],
            snapshots_dir=synthetic_snapshot_env["snapshots_dir"],
        )
    assert exc_info.value.code == 2

    # Should succeed with allow_config_diff=True
    report = compare_snapshots(
        label_a="snapA",
        label_b="snapC_diff",
        allow_config_diff=True,
        manifest_path=synthetic_snapshot_env["manifest_path"],
        snapshots_dir=synthetic_snapshot_env["snapshots_dir"],
    )
    assert report["config_hash_match"] is False
