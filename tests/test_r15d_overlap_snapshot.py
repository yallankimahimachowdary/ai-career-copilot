from pathlib import Path
from scripts.check_dataset_overlap import audit_role_family_coverage
from scripts.job_snapshot import load_snapshot

def test_snapshot_total_jobs_is_432():
    snapshot_path = Path("data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl")
    assert snapshot_path.exists(), f"Snapshot not found at {snapshot_path}"
    
    jobs, meta = load_snapshot(str(snapshot_path))
    assert len(jobs) == 432, f"Expected exactly 432 jobs, found {len(jobs)}"
    
    cov = audit_role_family_coverage(jobs)
    assert cov["total_jobs"] == 432
    
    breakdown = cov["breakdown"]
    assert breakdown["Data/AI"]["count"] == 117
    assert breakdown["Web/Software"]["count"] == 117
    assert breakdown["Cybersecurity/Cloud"]["count"] == 62
    assert breakdown["Mobile/UI-UX"]["count"] == 7
    assert breakdown["Electrical"]["count"] == 16
    assert breakdown["Mechanical"]["count"] == 20
    assert breakdown["Civil"]["count"] == 0
    assert breakdown["Commerce/Finance"]["count"] == 14
    assert breakdown["Arts/Media"]["count"] == 2
    assert breakdown["Other/Unclassified"]["count"] == 77
