import json
from pathlib import Path
import pytest

from scripts.make_results_tables import export_all_tables


def test_table_provenance_enforces_taxonomy_v2_1(tmp_path):
    """Verify that export_all_tables prints taxonomy v2.1 and fails if another version is present."""
    toy_report = {
        "run_type": "dryrun",
        "toy_fixture": True,
        "metadata": {
            "taxonomy_version": "v2.1",
            "taxonomy_hash": "34203073A38633314606663838D536C09F77E8C9C2507F1CEE98096DD98F2A1C",
        },
        "metrics": {
            "bm25": {"evaluated_candidates": 10},
            "sbert": {"evaluated_candidates": 10},
            "hybrid": {"evaluated_candidates": 10},
            "hybrid_llm_ollama": {"evaluated_candidates": 10},
            "hybrid_llm_gemini": {"evaluated_candidates": 10},
        },
    }

    report_file = tmp_path / "toy_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(toy_report, f)

    out_dir = tmp_path / "tables"
    export_all_tables(report_file, output_dir=out_dir, allow_dryrun=True)

    summary_file = out_dir / "results_tables_summary.md"
    assert summary_file.exists()
    content = summary_file.read_text(encoding="utf-8")

    # Assert taxonomy version is strictly v2.1 and hash matches
    assert "Taxonomy:** `v2.1`" in content
    assert "34203073A38633314606663838D536C09F77E8C9C2507F1CEE98096DD98F2A1C" in content
    assert "v1.2" not in content
