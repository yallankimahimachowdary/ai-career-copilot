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
    
    # Assert n=2 appears for test split in table 1
    assert "| BM25 | Test Split | 2 |" in md1 or '"BM25","Test Split","2"' in csv1
    
    # Assert n=2 appears in table 2 (old code hardcoded "33")
    assert '"SBERT-only (Dense Semantics)","2"' in csv2 or "| SBERT-only (Dense Semantics) | 2 |" in md2


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
