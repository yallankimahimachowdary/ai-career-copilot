import json
from pathlib import Path
import pytest
from scripts.check_dataset_overlap import audit_60_job_universe_overlap_and_leakage

def test_toy_manifest_split_and_leakage_detection():
    """
    S4 Test for Item 2: Verify overlap audit on toy manifest.
    Asserts pairwise test count calculation: 3 test candidates -> 3 pairs.
    Asserts dev leakage detection when test candidate universe is identical to dev universe.
    """
    dev_resumes = [
        {"candidate_id": "DEV_01", "universe_job_ids": ["job_1", "job_2", "job_3"]}
    ]
    test_resumes = [
        {"candidate_id": "TEST_01", "universe_job_ids": ["job_10", "job_11"]},
        {"candidate_id": "TEST_02", "universe_job_ids": ["job_20", "job_21"]},
        {"candidate_id": "TEST_03_LEAKED", "universe_job_ids": ["job_1", "job_2", "job_3"]}, # identical to DEV_01!
    ]
    
    # We test with pre-supplied universe_job_ids
    # Old code tried to rank jobs via BM25 instead of using existing candidate_universes job sets
    # We test our function detecting leakage
    from scripts.check_dataset_overlap import audit_fixed_universe_overlap
    
    res = audit_fixed_universe_overlap(test_resumes, dev_resumes)
    
    # Pairwise test combinations: 3 * 2 / 2 = 3 pairs
    assert len(res["pairwise_overlaps"]) == 3
    # Dev checks: 3 * 1 = 3 checks
    assert len(res["dev_set_leakage_checks"]) == 3
    # Leakage must be detected for TEST_03_LEAKED
    assert res["leakage_detected"] is True
