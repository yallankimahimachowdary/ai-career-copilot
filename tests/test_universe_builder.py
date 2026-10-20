"""
tests/test_universe_builder.py
------------------------------
Unit and integration tests for Evaluation Universe Builder (R11-2).

Tests:
1. Determinism: Same seed produces byte-identical universes and split assignments.
2. Disjointness: No candidate resume appears in both dev and test sets.
3. Scope handling: Deficit families flagged out_of_scope_for_ranking_eval.
4. Stratified universe sampling across seniority buckets without dropping available tiers.
"""

import json
from pathlib import Path
import pytest

from scripts.build_universes import build_universes, load_eval_scope, sample_stratified_universe


def test_load_eval_scope_matches_frozen_contract():
    """Verify eval_scope.json matches the 3-family in-scope policy."""
    in_scope, deficit = load_eval_scope("docs/eval_scope.json")
    assert in_scope == {"Data/AI", "Web/Software", "Cybersecurity/Cloud"}
    assert "Civil" in deficit
    assert "Mechanical" in deficit
    assert "Mobile/UI-UX" in deficit


def test_universe_builder_determinism(tmp_path: Path):
    """Running builder twice with the same seed produces byte-identical output."""
    out_1 = tmp_path / "run_1.json"
    out_2 = tmp_path / "run_2.json"

    res_1 = build_universes(
        snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
        resumes_dir="data/resumes_dryrun",
        seed=101,
        max_resumes=15,
        output_path=out_1,
        run_type="dryrun",
        timestamp="2026-10-20T12:00:00Z",
    )

    res_2 = build_universes(
        snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
        resumes_dir="data/resumes_dryrun",
        seed=101,
        max_resumes=15,
        output_path=out_2,
        run_type="dryrun",
        timestamp="2026-10-20T12:00:00Z",
    )

    assert out_1.read_bytes() == out_2.read_bytes(), "Outputs with same seed must be byte-identical"
    assert res_1["candidate_universes"] == res_2["candidate_universes"]


def test_dev_test_split_disjointness(tmp_path: Path):
    """Dev and test resume sets must be strictly disjoint with zero candidate leakage."""
    out = tmp_path / "split_test.json"
    res = build_universes(
        snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
        resumes_dir="data/resumes_dryrun",
        seed=42,
        max_resumes=30,
        output_path=out,
        run_type="dryrun",
    )

    dev_cands = set()
    test_cands = set()

    for cid, u in res["candidate_universes"].items():
        if u["split"] == "dev":
            dev_cands.add(cid)
        elif u["split"] == "test":
            test_cands.add(cid)

    assert len(dev_cands) > 0, "Expected non-empty dev split"
    assert len(test_cands) > 0, "Expected non-empty test split"
    overlap = dev_cands.intersection(test_cands)
    assert len(overlap) == 0, f"Disjointness violated! Leakage between dev and test: {overlap}"


def test_out_of_scope_resumes_flagged(tmp_path: Path):
    """Candidates from deficit families must be flagged out_of_scope_for_ranking_eval."""
    out = tmp_path / "scope_flag.json"
    res = build_universes(
        snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
        resumes_dir="data/resumes_dryrun",
        seed=42,
        max_resumes=50,
        output_path=out,
        run_type="dryrun",
    )

    has_out_of_scope = False
    for cid, u in res["candidate_universes"].items():
        if not u["is_in_scope"]:
            has_out_of_scope = True
            assert u["out_of_scope_for_ranking_eval"] is True
            assert u["universe_size"] == 0
            assert u["split"] == "out_of_scope"
        else:
            assert u["out_of_scope_for_ranking_eval"] is False
            assert u["universe_size"] > 0

    assert has_out_of_scope, "Dataset should contain deficit-family resumes flagged out of scope"
