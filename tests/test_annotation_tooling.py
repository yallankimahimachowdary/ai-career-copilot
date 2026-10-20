"""
tests/test_annotation_tooling.py
--------------------------------
Unit tests for Blinded Annotation Tooling and Ingestion (R11-3).

Tests:
1. Sheet blinding: CSV sheets contain zero model scores/ranks/predicted salaries and start with blank ratings.
2. Ingestion validation: Rejection of invalid ratings, blank ratings, and duplicate pairs.
3. Agreement metrics: Quadratic weighted kappa and raw agreement match ground truth on toy fixtures.
4. Adjudication precedence: Adjudicated values take priority over individual raters.
"""

import csv
import json
from pathlib import Path
import pytest

from scripts.ingest_annotations import (
    AnnotationValidationError,
    compute_quadratic_weighted_kappa,
    bootstrap_kappa_ci,
    ingest_annotations,
    read_and_validate_annotation_sheet,
)
from scripts.make_annotation_sheets import assign_raters, make_annotation_sheets


def test_assign_raters_balance_and_overlap():
    """Verify rater assignment allocates 8 double-rated resumes and balances the remainder."""
    candidates = [f"CAND_{i:03d}" for i in range(1, 21)]
    assignments = assign_raters(candidates, seed=42, num_double_rated=8)

    assert len(assignments["double_rated_candidates"]) == 8
    assert assignments["counts"]["double_rated_count"] == 8
    # 20 - 8 = 12 remainder -> 6 to A, 6 to B
    assert len(assignments["rater_a_candidates"]) == 14  # 8 + 6
    assert len(assignments["rater_b_candidates"]) == 14  # 8 + 6
    assert set(assignments["double_rated_candidates"]).issubset(set(assignments["rater_a_candidates"]))
    assert set(assignments["double_rated_candidates"]).issubset(set(assignments["rater_b_candidates"]))


def test_sheet_blinding_and_blank_ratings(tmp_path: Path):
    """Generated CSV sheets must have blank ratings and exclude all algorithm scores/ranks/salaries."""
    # Create toy universe JSON
    toy_univ = tmp_path / "toy_universes.json"
    univ_payload = {
        "candidate_universes": {
            "CAND_001": {
                "candidate_id": "CAND_001",
                "role_family": "Web/Software",
                "is_in_scope": True,
                "out_of_scope_for_ranking_eval": False,
                "job_ids": ["job-1", "job-2"],
            }
        }
    }
    toy_univ.write_text(json.dumps(univ_payload), encoding="utf-8")

    # Generate sheets
    manifest = make_annotation_sheets(
        universes_json_path=toy_univ,
        snapshot_path="data/snapshots/jobs_snapshot_1_20261019_adzuna.jsonl",
        output_dir=tmp_path / "sheets",
        seed=42,
        num_double_rated=1,
        run_type="dryrun",
    )

    sheet_a_csv = tmp_path / "sheets" / "annotation_sheet_rater_a_dryrun.csv"
    assert sheet_a_csv.exists()

    with open(sheet_a_csv, "r", encoding="utf-8") as f:
        lines = f.readlines()
        # Verify header instructions include 0, 1, 2 scale
        assert any("0 = Not relevant" in l for l in lines)
        assert any("1 = Partially relevant" in l for l in lines)
        assert any("2 = Strong fit" in l for l in lines)

    # Check data rows: no algorithmic fields and blank rating
    with open(sheet_a_csv, "r", encoding="utf-8") as f:
        data_lines = [l for l in f if not l.startswith("#")]
        reader = csv.DictReader(data_lines)
        assert "score" not in reader.fieldnames
        assert "rank" not in reader.fieldnames
        assert "predicted_salary" not in reader.fieldnames
        assert "similarity" not in reader.fieldnames
        for row in reader:
            assert row["rating"] == "", "Rating column must be strictly blank upon generation"


def test_ingestion_validation_rejections(tmp_path: Path):
    """Validation rejects blank ratings, invalid ratings, and duplicate pairs."""
    sheet_invalid = tmp_path / "sheet_invalid.csv"

    # 1. Blank rating rejection
    sheet_invalid.write_text(
        "resume_alias,job_id,rating\nCAND_001,job-1,\n", encoding="utf-8"
    )
    with pytest.raises(AnnotationValidationError, match="BLANK rating"):
        read_and_validate_annotation_sheet(sheet_invalid, rater_id="rater_a")

    # 2. Out-of-bounds rating rejection (3 is outside {0, 1, 2})
    sheet_invalid.write_text(
        "resume_alias,job_id,rating\nCAND_001,job-1,3\n", encoding="utf-8"
    )
    with pytest.raises(AnnotationValidationError, match="Must be strictly in"):
        read_and_validate_annotation_sheet(sheet_invalid, rater_id="rater_a")

    # 3. Duplicate pair rejection
    sheet_invalid.write_text(
        "resume_alias,job_id,rating\nCAND_001,job-1,2\nCAND_001,job-1,1\n", encoding="utf-8"
    )
    with pytest.raises(AnnotationValidationError, match="Duplicate"):
        read_and_validate_annotation_sheet(sheet_invalid, rater_id="rater_a")


def test_toy_agreement_metrics_and_adjudication(tmp_path: Path):
    """Evaluate kappa, agreement, and adjudication precedence on toy data."""
    sheet_a = tmp_path / "sheet_a.csv"
    sheet_b = tmp_path / "sheet_b.csv"

    # Perfect agreement for 4 items, disagreement on 1 item
    sheet_a.write_text(
        "resume_alias,job_id,rating,notes\n"
        "CAND_1,J1,2,strong match\n"
        "CAND_1,J2,1,partial\n"
        "CAND_1,J3,0,irrelevant\n"
        "CAND_1,J4,2,fit\n"
        "CAND_1,J5,1,borderline\n",
        encoding="utf-8"
    )
    sheet_b.write_text(
        "resume_alias,job_id,rating,notes\n"
        "CAND_1,J1,2,agreed\n"
        "CAND_1,J2,1,agreed\n"
        "CAND_1,J3,0,agreed\n"
        "CAND_1,J4,2,agreed\n"
        "CAND_1,J5,0,disagreed\n",
        encoding="utf-8"
    )

    out_labels = tmp_path / "labels.jsonl"
    out_dis = tmp_path / "disagreements.csv"

    res = ingest_annotations(
        sheet_a_path=sheet_a,
        sheet_b_path=sheet_b,
        output_labels_path=out_labels,
        disagreements_path=out_dis,
        run_type="dryrun",
        seed=42,
    )

    assert res["total_labels_written"] == 5
    assert res["double_rated_items"] == 5
    assert res["raw_agreement_rate"] == 0.80  # 4 of 5 match
    assert res["disagreements_count"] == 1
    assert res["quadratic_weighted_kappa"] > 0.60
    assert len(res["kappa_95_ci"]) == 2

    # Verify disagreements CSV written
    assert out_dis.exists()
    with open(out_dis, "r", encoding="utf-8") as f:
        dis_rows = list(csv.DictReader(f))
        assert len(dis_rows) == 1
        assert dis_rows[0]["job_id"] == "J5"
        assert dis_rows[0]["rater_a_rating"] == "1"
        assert dis_rows[0]["rater_b_rating"] == "0"

    # Test adjudication precedence
    adj_file = tmp_path / "adjudications.csv"
    adj_file.write_text(
        "resume_id,job_id,adjudicated_rating\nCAND_1,J5,2\n", encoding="utf-8"
    )

    res_adj = ingest_annotations(
        sheet_a_path=sheet_a,
        sheet_b_path=sheet_b,
        output_labels_path=out_labels,
        adjudication_path=adj_file,
        run_type="dryrun",
        seed=42,
    )
    assert res_adj["adjudications_applied"] == 1

    # Verify the label file used the adjudicated value 2 for J5
    with open(out_labels, "r", encoding="utf-8") as f:
        labels = [json.loads(line) for line in f]
        j5_label = next(l for l in labels if l["job_id"] == "J5")
        assert j5_label["rating"] == 2
        assert j5_label["source"] == "adjudicated"
