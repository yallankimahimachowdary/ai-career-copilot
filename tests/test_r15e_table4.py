import json
from pathlib import Path
import shutil
import pytest
from scripts.make_results_tables import build_table_4, parse_phase_b_logs


def test_warm_latency_median_from_repo_bm25_json(tmp_path):
    """
    R15e Item 1 S4 requirement:
    Feed a copy of bm25.json from the repo into parse_phase_b_logs / build_table_4,
    assert warm latency is strictly 12.93 ms (median of [13.85, 12.01]).
    """
    repo_bm25 = Path("results/dryrun/phase_b_ranking/bm25.json")
    assert repo_bm25.exists(), f"Expected repo bm25.json to exist at {repo_bm25}"

    # Copy bm25.json into temporary logs directory
    test_logs_dir = tmp_path / "phase_b"
    test_logs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(repo_bm25, test_logs_dir / "bm25.json")

    summary = parse_phase_b_logs(test_logs_dir)
    assert "bm25" in summary
    assert summary["bm25"]["warm_latency_ms"] == 12.93

    toy_report = {"run_type": "dryrun", "metrics": {}}
    md4, csv4 = build_table_4(toy_report, is_dryrun=True, logs_dir=test_logs_dir)
    assert "12.93 ms" in md4 or '"12.93 ms"' in csv4


def test_peak_rss_from_log_prints_value(tmp_path):
    """
    R15e Item 2 S4 requirement:
    A toy log with peak_rss_python_mb=123.4 prints 123.4 (or 123.4 MB) in Table 4.
    """
    test_logs_dir = tmp_path / "phase_b"
    test_logs_dir.mkdir(parents=True, exist_ok=True)

    toy_log = {
        "method": "bm25",
        "first_call_latency_ms": 10.0,
        "subsequent_latencies_ms": [12.0, 14.0],
        "prompt_version": "v1.1",
        "prompt_tokens": 150,
        "response_tokens": 0,
        "peak_rss_python_mb": 123.4,
        "peak_rss_ollama_mb": 0.0,
        "n_resumes": 1,
    }
    with open(test_logs_dir / "bm25.json", "w", encoding="utf-8") as f:
        json.dump(toy_log, f)

    toy_report = {"run_type": "dryrun", "metrics": {}}
    md4, csv4 = build_table_4(toy_report, is_dryrun=True, logs_dir=test_logs_dir)

    assert "123.4" in md4 or '"Python: 123.4 MB"' in csv4
