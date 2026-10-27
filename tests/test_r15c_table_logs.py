import json
from pathlib import Path
import pytest
from scripts.make_results_tables import build_table_1, build_table_2, build_table_4

def test_toy_report_with_2_evaluated_resumes_prints_n_equals_2():
    """
    S4 requirement: toy report with 2 evaluated resumes prints n=2 (fails on old code).
    Old code hardcoded n=33 (or defaulted to 33) in table 1 and table 2.
    """
    toy_report = {
        "run_type": "dryrun",
        "toy_fixture": True,
        "metrics": {
            "bm25": {"evaluated_candidates": 2, "ndcg@10": 0.50},
            "sbert": {"evaluated_candidates": 2, "ndcg@10": 0.60},
            "hybrid": {"evaluated_candidates": 2, "ndcg@10": 0.70},
            "hybrid_llm_ollama": {"evaluated_candidates": 2, "ndcg@10": 0.75},
            "hybrid_llm_gemini": {"evaluated_candidates": 2, "ndcg@10": 0.80},
        },
        "ablations": {
            "sbert_only": {"evaluated_candidates": 2},
            "overlap_only": {"evaluated_candidates": 2},
            "hybrid_no_overlap": {"evaluated_candidates": 2},
            "random_reorder": {"evaluated_candidates": 2},
            "seniority_gate_on": {"evaluated_candidates": 2},
            "seniority_gate_off": {"evaluated_candidates": 2},
        }
    }
    
    md1, csv1 = build_table_1(toy_report, is_dryrun=True)
    md2, csv2 = build_table_2(toy_report, is_dryrun=True)
    md4, csv4 = build_table_4(toy_report, is_dryrun=True)
    
    # Assert n=2 appears for test split in table 1
    assert "| BM25 | Test Split | 2 |" in md1 or '"BM25","Test Split","2"' in csv1
    
    # Assert n=2 appears in table 2 (old code hardcoded "33")
    assert '"SBERT-only (Dense Semantics)","2"' in csv2 or "| SBERT-only (Dense Semantics) | 2 |" in md2

    # Assert n=2 appears in table 4 for toy report
    assert '"BM25","None (Lexical)","2"' in csv4 or "| BM25 | None (Lexical) | 2 |" in md4


def test_missing_latency_logs_prints_na(tmp_path):
    """
    S4 requirement: toy report missing latency logs prints 'n/a'.
    Old code hardcoded '12.40 ms', '11.80 ms', '1,240' etc. regardless of missing logs.
    """
    empty_logs_dir = tmp_path / "empty_phase_b"
    empty_logs_dir.mkdir(parents=True, exist_ok=True)
    
    toy_report = {
        "run_type": "dryrun",
        "metrics": {},
    }
    
    md4, csv4 = build_table_4(toy_report, is_dryrun=True, logs_dir=empty_logs_dir)
    
    # Assert cold and warm latency for BM25 and others print "n/a", not "12.40 ms"
    assert "12.40 ms" not in md4
    assert "840.50 ms" not in md4
    assert "n/a" in md4


def test_warm_latency_median_of_later_calls(tmp_path):
    """
    S4 requirement: warm latency of [13.85, 12.01] prints 12.93.
    """
    logs_dir = tmp_path / "phase_b"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Write a test log with cold call = 9.99, and later calls = [13.85, 12.01]
    for idx, (ts, lat) in enumerate([("2026-10-20T10:00:00Z", 9.99), ("2026-10-20T10:01:00Z", 13.85), ("2026-10-20T10:02:00Z", 12.01)]):
        entry = {
            "inputs": {"candidate_id": f"SYN_00{idx+1}"},
            "outputs": {
                "method": "bm25",
                "run_metadata": {
                    "latency_ms": lat,
                    "prompt_version": "v1.1",
                    "prompt_tokens": 180,
                    "response_tokens": 0,
                }
            },
            "provenance": {"timestamp": ts}
        }
        with open(logs_dir / f"SYN_00{idx+1}_rep0_bm25.json", "w", encoding="utf-8") as f:
            json.dump(entry, f)
            
    toy_report = {"run_type": "dryrun", "metrics": {}}
    md4, csv4 = build_table_4(toy_report, is_dryrun=True, logs_dir=logs_dir)
    assert "12.93 ms" in md4 or '"12.93 ms"' in csv4
