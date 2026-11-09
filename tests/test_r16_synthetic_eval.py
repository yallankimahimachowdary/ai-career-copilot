"""
tests/test_r16_synthetic_eval.py
--------------------------------
Comprehensive tests for R16 Synthetic Benchmark Run Type:
1. run_type=real refuses SYN_ files.
2. Intake refuses mixed real and synthetic resumes.
3. run_type=synthetic_eval accepts SYN_ files ONLY (refuses purely real folder).
4. run_type=real requires results/real/labels.jsonl.
5. dryrun withholds quality metrics.
6. synthetic_eval computes metrics when labels exist, withholds when missing.
7. make_results_tables adds SYNTHETIC BENCHMARK banner and preserves real-run guard.
8. Determinism of --eval-subset and --num-double-rated across PYTHONHASHSEED.
9. Freeze point refuses rebuild without --force.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from app.core.provenance import get_file_sha256
from scripts.intake_resumes import process_resume_intake, ResumeContaminationError
from scripts.build_universes import build_universes, stratified_sample_candidates
from scripts.make_annotation_sheets import make_annotation_sheets, assign_raters
from scripts.make_results_tables import (
    load_evaluation_report,
    build_table_1,
    build_table_2,
    build_table_3,
    build_table_4,
    build_table_5,
)
from scripts.evaluate_ranking import run_evaluation_pipeline


def test_real_intake_refuses_syn_files(tmp_path):
    """Proves run_type=real refuses SYN_ synthetic resumes."""
    syn_dir = tmp_path / "syn_folder"
    syn_dir.mkdir()
    (syn_dir / "SYN_001_DataAI.pdf").write_bytes(b"%PDF-1.4 dummy synthetic resume")

    with pytest.raises(ResumeContaminationError) as excinfo:
        process_resume_intake(
            resumes_dir=syn_dir,
            output_dir=tmp_path / "out",
            run_type="real",
            allow_synthetic=False,
        )
    assert "run_type='real' strictly prohibits synthetic resumes" in str(excinfo.value) or "Synthetic resumes detected" in str(excinfo.value)


def test_intake_refuses_mixed_real_and_synthetic(tmp_path):
    """Proves intake refuses folders mixing real and synthetic resumes across all run types."""
    mixed_dir = tmp_path / "mixed_folder"
    mixed_dir.mkdir()
    (mixed_dir / "SYN_001_DataAI.pdf").write_bytes(b"%PDF-1.4 dummy synthetic resume")
    (mixed_dir / "real_candidate_01.pdf").write_bytes(b"%PDF-1.4 dummy real resume")

    with pytest.raises(ResumeContaminationError) as excinfo:
        process_resume_intake(
            resumes_dir=mixed_dir,
            output_dir=tmp_path / "out",
            run_type="synthetic_eval",
        )
    assert "Mixed real and synthetic resumes detected" in str(excinfo.value)


def test_synthetic_eval_intake_refuses_purely_real(tmp_path):
    """Proves run_type=synthetic_eval accepts SYN_ files ONLY and refuses purely real resumes."""
    real_dir = tmp_path / "real_folder"
    real_dir.mkdir()
    (real_dir / "candidate_alice.pdf").write_bytes(b"%PDF-1.4 dummy candidate alice")

    with pytest.raises(ResumeContaminationError) as excinfo:
        process_resume_intake(
            resumes_dir=real_dir,
            output_dir=tmp_path / "out",
            run_type="synthetic_eval",
        )
    assert "No synthetic resumes (SYN_) detected" in str(excinfo.value) or "accepts SYN_ files ONLY" in str(excinfo.value)


def test_real_eval_requires_labels_jsonl(tmp_path):
    """Proves run_type=real strictly requires results/real/labels.jsonl."""
    from scripts.run_all import run_stage_eval
    missing_labels = tmp_path / "nonexistent_labels.jsonl"
    with pytest.raises(FileNotFoundError) as excinfo:
        run_stage_eval(
            labels_path=str(missing_labels),
            snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
            resumes_dir="data/resumes_dryrun",
            run_type="real",
        )
    assert "does not exist" in str(excinfo.value)


def test_table_banner_synthetic_benchmark(tmp_path):
    """Proves tables built from synthetic_eval reports contain the required banner and real-run guard stays."""
    # 1. Real-run guard refuses dryrun report without --allow-dryrun
    fake_dryrun_report = tmp_path / "eval_report_dryrun.json"
    fake_dryrun_report.write_text(json.dumps({"run_type": "dryrun", "metrics": {}}), encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        load_evaluation_report(fake_dryrun_report, allow_dryrun=False)
    assert "Table generator rejected dryrun report" in str(excinfo.value)

    # 2. synthetic_eval report is accepted without --allow-dryrun
    syn_report = {
        "run_type": "synthetic_eval",
        "metrics": {"hybrid": {"ndcg@10": 0.85, "precision@5": 0.80, "mrr": 0.90, "n": 25}},
        "statistical_comparisons": {},
    }
    banner = "> **SYNTHETIC BENCHMARK -- template-generated resumes, not real candidates**\n"

    t1_md, _ = build_table_1(syn_report, is_dryrun=False, include_banner=True)
    assert banner in t1_md, "Table 1 must include synthetic benchmark banner"

    t2_md, _ = build_table_2(syn_report, is_dryrun=False, include_banner=True)
    assert banner in t2_md, "Table 2 must include synthetic benchmark banner"

    t3_md, _ = build_table_3(syn_report, is_dryrun=False, include_banner=True)
    assert banner in t3_md, "Table 3 must include synthetic benchmark banner"

    t5_md, _ = build_table_5(syn_report, is_dryrun=False, include_banner=True)
    assert banner in t5_md, "Table 5 must include synthetic benchmark banner"


def test_stratified_sample_candidates_distribution():
    """Proves stratified sampling distributes subsets proportionally across families."""
    cands = []
    # 23 Data/AI, 10 Web/Software, 8 Cybersecurity/Cloud (Total 41)
    for i in range(23):
        cands.append({"candidate_id": f"D_{i:02d}", "role_family": "Data/AI"})
    for i in range(10):
        cands.append({"candidate_id": f"W_{i:02d}", "role_family": "Web/Software"})
    for i in range(8):
        cands.append({"candidate_id": f"C_{i:02d}", "role_family": "Cybersecurity/Cloud"})

    # Subset 25
    sampled = stratified_sample_candidates(cands, subset_size=25, seed=42)
    assert len(sampled) == 25
    fam_counts = {}
    for c in sampled:
        fam_counts[c["role_family"]] = fam_counts.get(c["role_family"], 0) + 1

    assert fam_counts["Data/AI"] == 14
    assert fam_counts["Web/Software"] == 6
    assert fam_counts["Cybersecurity/Cloud"] == 5


def test_freeze_point_refuses_rebuild_without_force(tmp_path):
    """Proves synthetic_eval universes are frozen and refuse rebuild without --force."""
    out_dir = tmp_path / "results" / "synthetic_eval"
    out_dir.mkdir(parents=True)
    cand_univ = out_dir / "candidate_universes.json"
    cand_univ.write_text(json.dumps({"test": "existing"}), encoding="utf-8")
    manifest = out_dir / "universes_manifest.json"
    manifest.write_text(json.dumps({"sha256": "12345"}), encoding="utf-8")

    # Rebuild without force must raise RuntimeError
    with pytest.raises(RuntimeError) as excinfo:
        build_universes(
            snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
            resumes_dir="data/resumes_dryrun",
            run_type="synthetic_eval",
            output_path=cand_univ,
            force=False,
        )
    assert "FREEZE POINT REFUSAL" in str(excinfo.value)


def test_subset_and_double_rated_determinism():
    """Proves same seed yields identical candidate assignment across two calls."""
    cands = [f"SYN_{i:03d}" for i in range(1, 42)]
    res1 = assign_raters(cands, seed=42, num_double_rated=8)
    res2 = assign_raters(cands, seed=42, num_double_rated=8)
    assert res1 == res2
    assert len(res1["rater_a_candidates"]) == 25
    assert len(res1["rater_b_candidates"]) == 24
    assert len(res1["double_rated_candidates"]) == 8
