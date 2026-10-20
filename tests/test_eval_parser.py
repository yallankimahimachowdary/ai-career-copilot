"""
tests/test_eval_parser.py
-------------------------
Unit tests for Parser Evaluation Tooling and Blank Gold Template (R11-4).

Tests:
1. Gold format parsing (JSONL and JSON formats).
2. Metric computation: Micro and Macro Precision, Recall, and F1 match mathematical expectation.
3. Bootstrap confidence intervals produce valid bounds [low, high].
4. Blank gold template generator: Generates requested sample size with 100% blank predictions.
"""

import csv
import json
from pathlib import Path
import pytest

from scripts.eval_parser import (
    bootstrap_prf1_ci,
    compute_prf1,
    evaluate_parser,
    generate_gold_template_csv,
    load_gold_annotations,
)


def test_compute_prf1_exact():
    """Verify precision, recall, and F1 calculations on controlled sets."""
    pred = {"python", "sql", "docker"}
    gold = {"python", "sql", "fastapi", "git"}

    # TP = 2, Pred = 3 -> P = 2/3 = 0.6667
    # Gold = 4 -> R = 2/4 = 0.5000
    # F1 = 2 * (2/3 * 1/2) / (2/3 + 1/2) = (2/3) / (7/6) = 4/7 = 0.5714
    p, r, f1 = compute_prf1(pred, gold)
    assert p == 0.6667
    assert r == 0.5000
    assert f1 == 0.5714

    # Empty sets
    assert compute_prf1(set(), set()) == (1.0, 1.0, 1.0)
    assert compute_prf1(set(), {"python"}) == (0.0, 0.0, 0.0)


def test_load_gold_annotations_json_and_jsonl(tmp_path: Path):
    """Support both JSON list/dict and line-delimited JSONL gold files."""
    jsonl_file = tmp_path / "gold.jsonl"
    jsonl_file.write_text(
        json.dumps({"resume_id": "RES_1", "skills": ["Python", "SQL"]}) + "\n" +
        json.dumps({"resume_id": "RES_2", "skills": ["Docker", "Linux"]}) + "\n",
        encoding="utf-8"
    )

    entries_jsonl = load_gold_annotations(jsonl_file)
    assert len(entries_jsonl) == 2
    assert entries_jsonl[0]["resume_id"] == "RES_1"
    assert entries_jsonl[0]["skills"] == ["Python", "SQL"]

    json_file = tmp_path / "gold.json"
    json_file.write_text(
        json.dumps({
            "resumes": [
                {"resume_file": "RES_3.pdf", "skills": ["Java", "Spring Boot"]}
            ]
        }),
        encoding="utf-8"
    )
    entries_json = load_gold_annotations(json_file)
    assert len(entries_json) == 1
    assert entries_json[0]["resume_id"] == "RES_3.pdf"
    assert entries_json[0]["skills"] == ["Java", "Spring Boot"]


def test_bootstrap_prf1_ci_bounds():
    """Bootstrap CI returns valid lower and upper bounds."""
    toy_sample = [
        {"tp": 3.0, "pred_count": 4.0, "gold_count": 5.0, "precision": 0.75, "recall": 0.6, "f1": 0.6667},
        {"tp": 4.0, "pred_count": 5.0, "gold_count": 4.0, "precision": 0.80, "recall": 1.0, "f1": 0.8889},
        {"tp": 2.0, "pred_count": 3.0, "gold_count": 3.0, "precision": 0.6667, "recall": 0.6667, "f1": 0.6667},
    ]
    ci = bootstrap_prf1_ci(toy_sample, n_resamples=100, seed=42)
    assert "micro_f1" in ci and "macro_f1" in ci
    low_mac, high_mac = ci["macro_f1"]
    assert 0.5 <= low_mac <= high_mac <= 1.0


def test_generate_blank_gold_template(tmp_path: Path):
    """Verify template generation produces blank predictions and covers families."""
    out_csv = tmp_path / "template.csv"
    res = generate_gold_template_csv(
        resumes_dir="data/resumes_dryrun",
        output_csv_path=out_csv,
        sample_size=10,
        seed=42,
    )

    assert res["total_resumes_sampled"] == 10
    assert out_csv.exists()

    with open(out_csv, "r", encoding="utf-8") as f:
        lines = [l for l in f if not l.startswith("#")]
        reader = list(csv.DictReader(lines))
        assert len(reader) == 10
        for row in reader:
            assert row["gold_skills_comma_separated"] == "", "Predictions must be strictly blank"
            assert len(row["resume_text_excerpt"]) > 20
