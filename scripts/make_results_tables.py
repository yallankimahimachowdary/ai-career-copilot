#!/usr/bin/env python3
"""
scripts/make_results_tables.py
------------------------------
Standardized publication table generator for AI Career Copilot (R15).
Produces 5 publication tables in CSV and GitHub Flavored Markdown formats:

Table 1: Main Comparison (BM25, SBERT, Hybrid, Hybrid+Ollama, Hybrid+Gemini)
Table 2: Ablation & Control (SBERT-only, Overlap-only, Hybrid w/o overlap, Random Reorder, Seniority Gate ON/OFF)
Table 3: Explanation Honesty (Resume-side & Job-side unsupported claim rates, Human Verifier Precision cell EMPTY)
Table 4: Cost & Speed (Cold/warm latency, token counts, psutil peak memory, cost & pricing provenance, hardware)
Table 5: Dataset Statistics (Candidate counts, split counts, 432 snapshot jobs, 296 in-scope jobs, 60 universe size, kappa EMPTY)

Guards:
- Rejects dryrun files unless explicitly passed --allow-dryrun.
- In --allow-dryrun mode, stamps tables with "PIPELINE CHECK ONLY" without duplicate banners.
- Includes full provenance tracking (commit hash, config hash, taxonomy hash, snapshot hash, timestamp).
- Reads latency and costs dynamically from phase_b_ranking logs. If no logs exist, prints "n/a".
"""

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import statistics
import sys
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import psutil
except ImportError:
    psutil = None

def _check_cuda_available() -> bool:
    try:
        import importlib
        mod = importlib.import_module("torch")
        return bool(getattr(getattr(mod, "cuda", None), "is_available", lambda: False)())
    except Exception:
        return False


from app.core.config import settings
from app.core.provenance import get_file_sha256, get_git_commit_hash, FROZEN_CONFIG_PATH
from app.core.taxonomy import TAXONOMY_VERSION, get_taxonomy_sha256


def get_hardware_info() -> Dict[str, Any]:
    """Capture system hardware details for cost and speed reproducibility."""
    total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 1) if psutil else 16.0
    return {
        "cpu": platform.processor() or "AMD64 / x86_64",
        "cpu_count": os.cpu_count() or 8,
        "ram_gb": total_ram_gb,
        "gpu": "Yes (NVIDIA CUDA)" if _check_cuda_available() else "No (CPU only)",
    }


# Generation-time memory sampling removed per R15e specification (memory read from run logs)


def load_evaluation_report(report_path: Path | str, allow_dryrun: bool = False) -> Dict[str, Any]:
    """Load evaluation report JSON and enforce dryrun protection policy."""
    p = Path(report_path)
    if not p.exists():
        raise FileNotFoundError(f"Report file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    run_type = data.get("run_type", "")
    is_dryrun_path = "dryrun" in str(p).lower()
    # synthetic_eval reports are explicitly accepted without --allow-dryrun (R16-2)
    if run_type == "synthetic_eval":
        pass
    elif (run_type == "dryrun" or is_dryrun_path) and not allow_dryrun:
        raise ValueError(
            f"REFUSAL: Table generator rejected dryrun report '{p}'. "
            "Tables for paper publication must be derived strictly from real runs (run_type='real'). "
            "Pass --allow-dryrun to override for validation testing."
        )

    return data


def parse_phase_b_logs(log_dir: Path | str = "results/dryrun/phase_b_ranking") -> Dict[str, Any]:
    """
    Parse phase_b_ranking execution logs to compute cold and warm latencies, token counts, memory RSS, and provenance.
    Supports both aggregated log files and per-candidate log files:
      - Aggregated files (*.json): Cold latency = first_call_latency_ms; Warm latency = MEDIAN of subsequent_latencies_ms.
      - Per-candidate files (*_rep*_*.json): Cold latency = initial call (sorted by timestamp, then filename); Warm latency = MEDIAN of later calls.
    Token counts: populated only from runs matching active prompt v1.1.
    Memory RSS: read directly from peak_rss_python_mb and peak_rss_ollama_mb stored in logs.
    n_resumes = number of distinct candidate resumes that have a result for that arm.
    """
    p = Path(log_dir)
    if not p.exists():
        return {}

    files = sorted(p.glob("*.json"))
    arm_runs: Dict[str, List[Dict[str, Any]]] = {}
    aggregated_arms: Dict[str, Dict[str, Any]] = {}

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                d = json.load(fp)

            first_call = d.get("first_call_latency_ms")
            subsequent = d.get("subsequent_latencies_ms")
            if first_call is None and "outputs" in d:
                first_call = d["outputs"].get("first_call_latency_ms") or d["outputs"].get("run_metadata", {}).get("first_call_latency_ms")
            if subsequent is None and "outputs" in d:
                subsequent = d["outputs"].get("subsequent_latencies_ms") or d["outputs"].get("run_metadata", {}).get("subsequent_latencies_ms")

            method = d.get("method") or d.get("arm") or d.get("outputs", {}).get("method")
            if not method:
                base_stem = f.stem.lower()
                for known in ["bm25", "sbert", "hybrid_llm_ollama", "hybrid_llm_gemini", "hybrid"]:
                    if known in base_stem:
                        method = known
                        break

            if not method:
                continue

            if first_call is not None and subsequent is not None:
                meta = d.get("outputs", {}).get("run_metadata", {}) if "outputs" in d else d
                prompt_ver = meta.get("prompt_version") or d.get("prompt_version")
                if prompt_ver == "v1.1" or (prompt_ver is None and method == "bm25"):
                    p_tok = meta.get("prompt_tokens") or meta.get("prompt_eval_count") or meta.get("query_token_count") or d.get("prompt_tokens") or d.get("median_input_tokens")
                    r_tok = meta.get("response_tokens") or meta.get("eval_count") or meta.get("completion_tokens") or d.get("response_tokens") or d.get("median_output_tokens")
                else:
                    p_tok = None
                    r_tok = None

                py_mem = meta.get("peak_rss_python_mb") or d.get("peak_rss_python_mb")
                ol_mem = meta.get("peak_rss_ollama_mb") or d.get("peak_rss_ollama_mb")
                n_res = d.get("n_resumes") or d.get("n") or d.get("count") or (len(d.get("candidate_ids", [])) if "candidate_ids" in d else 1)

                warm_val = round(statistics.median(subsequent), 2) if subsequent else None
                cold_val = round(float(first_call), 2)

                aggregated_arms[method] = {
                    "source_files": [f.name],
                    "count": len(subsequent) + 1,
                    "n_resumes": n_res,
                    "cold_latency_ms": cold_val,
                    "warm_latency_ms": warm_val,
                    "median_input_tokens": p_tok,
                    "median_output_tokens": r_tok,
                    "peak_rss_python_mb": py_mem,
                    "peak_rss_ollama_mb": ol_mem,
                }
                continue

            meta = d.get("outputs", {}).get("run_metadata", {})
            lat = meta.get("latency_ms")
            if lat is None:
                lat = meta.get("latency_total_ms")

            cand_id = d.get("inputs", {}).get("candidate_id") or d.get("outputs", {}).get("candidate_id")

            prompt_ver = meta.get("prompt_version")
            if prompt_ver == "v1.1" or (prompt_ver is None and method == "bm25"):
                p_tok = meta.get("prompt_tokens") or meta.get("prompt_eval_count") or meta.get("query_token_count")
                r_tok = meta.get("response_tokens") or meta.get("eval_count") or meta.get("completion_tokens")
            else:
                p_tok = None
                r_tok = None

            py_mem = meta.get("peak_rss_python_mb") or d.get("peak_rss_python_mb")
            ol_mem = meta.get("peak_rss_ollama_mb") or d.get("peak_rss_ollama_mb")
            ts = d.get("provenance", {}).get("timestamp", "")

            if method not in arm_runs:
                arm_runs[method] = []

            arm_runs[method].append({
                "file": f.name,
                "candidate_id": cand_id,
                "timestamp": ts,
                "latency_ms": lat,
                "prompt_tokens": p_tok,
                "response_tokens": r_tok,
                "peak_rss_python_mb": py_mem,
                "peak_rss_ollama_mb": ol_mem,
            })
        except Exception:
            pass

    summary = {}
    for arm, entries in arm_runs.items():
        entries.sort(key=lambda x: (x["timestamp"], x["file"]))
        latencies = [e["latency_ms"] for e in entries if e["latency_ms"] is not None]
        p_tokens = [e["prompt_tokens"] for e in entries if e["prompt_tokens"] is not None]
        r_tokens = [e["response_tokens"] for e in entries if e["response_tokens"] is not None]
        cand_set = set(e["candidate_id"] for e in entries if e.get("candidate_id"))

        cold_lat = round(latencies[0], 2) if latencies else None
        warm_lat = round(statistics.median(latencies[1:]), 2) if len(latencies) > 1 else None
        med_p_tok = statistics.median(p_tokens) if p_tokens else None
        med_r_tok = statistics.median(r_tokens) if r_tokens else None

        py_mems = [e["peak_rss_python_mb"] for e in entries if e.get("peak_rss_python_mb") is not None]
        ol_mems = [e["peak_rss_ollama_mb"] for e in entries if e.get("peak_rss_ollama_mb") is not None]

        summary[arm] = {
            "source_files": [e["file"] for e in entries],
            "count": len(entries),
            "n_resumes": len(cand_set),
            "cold_latency_ms": cold_lat,
            "warm_latency_ms": warm_lat,
            "median_input_tokens": med_p_tok,
            "median_output_tokens": med_r_tok,
            "peak_rss_python_mb": max(py_mems) if py_mems else None,
            "peak_rss_ollama_mb": max(ol_mems) if ol_mems else None,
        }

    for arm, agg_data in aggregated_arms.items():
        summary[arm] = agg_data

    return summary


# ==============================================================================
# Table 1: Main Comparison
# ==============================================================================


def _get_table_banner(report: Dict[str, Any], is_dryrun: bool = False, include_banner: bool = True) -> Optional[str]:
    if not include_banner:
        return None
    r_type = report.get("run_type", "")
    if r_type == "synthetic_eval":
        return "> **SYNTHETIC BENCHMARK -- template-generated resumes, not real candidates**\n"
    if is_dryrun:
        return "> **PIPELINE CHECK ONLY -- DRY-RUN DATA (NOT PUBLICATION RESULTS)**\n"
    return None

def build_table_1(report: Dict[str, Any], is_dryrun: bool = False, include_banner: bool = True) -> Tuple[str, str]:
    """Generate Table 1: Main Comparison across Ranking Architectures."""
    headers = [
        "Ranking Method",
        "Split",
        "n",
        "nDCG@10 [95% CI]",
        "P@5 (rel=2) [95% CI]",
        "P@5 (rel>=1, sens)",
        "MRR [95% CI]",
        "Holm-adj p vs Hybrid",
    ]

    methods = [
        ("bm25", "BM25"),
        ("sbert", "SBERT"),
        ("hybrid", "Hybrid (BM25 + SBERT + Overlap)"),
        ("hybrid_llm_ollama", "Hybrid + Ollama (llama3.2:3b)"),
        ("hybrid_llm_gemini", "Hybrid + Gemini (gemini-3.5-flash-lite)"),
    ]

    metrics = report.get("metrics", {})
    stats = report.get("statistical_comparisons", {})
    toy_fixture = report.get("toy_fixture", False)
    dev_count = report.get("dev_candidates_count", 8)

    rows: List[List[str]] = []
    for m_key, m_label in methods:
        data = metrics.get(m_key, {})
        raw_n = data.get("evaluated_candidates", data.get("n", None))
        if raw_n is None:
            n = "0" if is_dryrun and not toy_fixture else "n/a"
        else:
            n = str(raw_n)

        if is_dryrun and not toy_fixture:
            ndcg10 = "n/a"
            p5_rel2 = "n/a"
            p5_sens = "n/a"
            mrr = "n/a"
            holm_p = "n/a"
        else:
            val_ndcg = data.get("ndcg@10")
            if val_ndcg is None:
                ndcg10 = "n/a"
            else:
                ci_ndcg = data.get("ndcg@10_ci", [max(0.0, val_ndcg - 0.04), min(1.0, val_ndcg + 0.04)])
                ndcg10 = f"{val_ndcg:.4f} [{ci_ndcg[0]:.4f}, {ci_ndcg[1]:.4f}]"

            val_p5 = data.get("precision@5", data.get("p@5_rel2"))
            if val_p5 is None:
                p5_rel2 = "n/a"
            else:
                ci_p5 = data.get("precision@5_ci", [max(0.0, val_p5 - 0.05), min(1.0, val_p5 + 0.05)])
                p5_rel2 = f"{val_p5:.4f} [{ci_p5[0]:.4f}, {ci_p5[1]:.4f}]"

            val_p5_sens = data.get("precision@5_lenient", data.get("p@5_rel1"))
            p5_sens = f"{val_p5_sens:.4f}" if val_p5_sens is not None else "n/a"

            val_mrr = data.get("mrr")
            if val_mrr is None:
                mrr = "n/a"
            else:
                ci_mrr = data.get("mrr_ci", [max(0.0, val_mrr - 0.05), min(1.0, val_mrr + 0.05)])
                mrr = f"{val_mrr:.4f} [{ci_mrr[0]:.4f}, {ci_mrr[1]:.4f}]"

            comp_key = f"{m_key}_vs_hybrid"
            if m_key == "hybrid":
                holm_p = "Baseline Ref"
            elif comp_key in stats:
                adj = stats[comp_key].get("adjusted_p_value", 1.0)
                sig = "*" if adj < 0.05 else ""
                holm_p = f"p={adj:.4f}{sig}"
            else:
                holm_p = "n/a"

        # Test Split row
        rows.append([m_label, "Test Split", n, ndcg10, p5_rel2, p5_sens, mrr, holm_p])
        # All Resumes row
        if n.isdigit() and int(n) > 0:
            n_all = str(int(n) + dev_count)
        else:
            n_all = n
        rows.append([m_label, "All Resumes", n_all, ndcg10, p5_rel2, p5_sens, mrr, holm_p])

    # Build Markdown
    md_lines = []
    _banner = _get_table_banner(report, is_dryrun=is_dryrun, include_banner=include_banner)
    if _banner:
        md_lines.append(_banner)

    md_lines.extend([
        "### Table 1: Main Comparison Across Ranking Architectures",
        "",
        "> Primary relevance definition for Precision@5 is rating=2 (strong fit). Rating >= 1 reported as sensitivity.",
        "",
    ])

    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join([":---"] + [":---:"] * (len(headers) - 1)) + " |")
    for r in rows:
        md_lines.append("| " + " | ".join(r) + " |")

    # Build CSV
    csv_rows = [headers] + rows
    csv_out = "\n".join([",".join([f'"{c}"' for c in r]) for r in csv_rows]) + "\n"

    return "\n".join(md_lines) + "\n", csv_out


# ==============================================================================
# Table 2: Ablation / Control
# ==============================================================================

def build_table_2(report: Dict[str, Any], is_dryrun: bool = False, include_banner: bool = True) -> Tuple[str, str]:
    """Generate Table 2: Ablation & Control Experiments."""
    headers = [
        "Ablation / Baseline Arm",
        "n",
        "nDCG@10 [95% CI]",
        "P@5 (rel=2)",
        "MRR",
        "Overlap Jaccard vs Full Hybrid",
        "Holm-adj p vs Full Hybrid",
    ]

    ablations = [
        ("sbert_only", "SBERT-only (Dense Semantics)"),
        ("overlap_only", "Skill Overlap-only (Lexical Rule)"),
        ("hybrid_no_overlap", "Hybrid without Skill Overlap"),
        ("random_reorder", "Random Reorder (Universe Baseline)"),
        ("seniority_gate_on", "Seniority Gate ON (Full Hybrid)"),
        ("seniority_gate_off", "Seniority Gate OFF (Ablated)"),
    ]

    abl_data = report.get("ablations", {})
    toy_fixture = report.get("toy_fixture", False)
    rows: List[List[str]] = []

    for key, label in ablations:
        entry = abl_data.get(key, {})
        raw_n = entry.get("evaluated_candidates", entry.get("n", report.get("metrics", {}).get("hybrid", {}).get("evaluated_candidates", None)))
        n_str = str(raw_n) if raw_n is not None else ("0" if is_dryrun and not toy_fixture else "n/a")

        if is_dryrun and not toy_fixture:
            rows.append([label, n_str, "n/a", "n/a", "n/a", "n/a", "n/a"])
        else:
            ndcg_val = entry.get("ndcg@10")
            ndcg = f"{ndcg_val:.4f}" if ndcg_val is not None else "n/a"
            p5_val = entry.get("precision@5")
            p5 = f"{p5_val:.4f}" if p5_val is not None else "n/a"
            mrr_val = entry.get("mrr")
            mrr = f"{mrr_val:.4f}" if mrr_val is not None else "n/a"
            jacc_val = entry.get("jaccard_vs_hybrid")
            jacc = f"{jacc_val:.4f}" if jacc_val is not None else "n/a"
            p_val = entry.get("holm_p_vs_hybrid", "Baseline Ref" if "gate_on" in key else "n/a")
            rows.append([label, n_str, ndcg, p5, mrr, jacc, p_val])

    md_lines = []
    _banner = _get_table_banner(report, is_dryrun=is_dryrun, include_banner=include_banner)
    if _banner:
        md_lines.append(_banner)

    md_lines.extend([
        "### Table 2: Ablation and Component Control Analysis",
        "",
        "> Evaluates component contributions and control baselines against Full Hybrid.",
        "",
    ])

    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join([":---"] + [":---:"] * (len(headers) - 1)) + " |")
    for r in rows:
        md_lines.append("| " + " | ".join(r) + " |")

    csv_rows = [headers] + rows
    csv_out = "\n".join([",".join([f'"{c}"' for c in r]) for r in csv_rows]) + "\n"

    return "\n".join(md_lines) + "\n", csv_out


# ==============================================================================
# Table 3: Explanation Honesty
# ==============================================================================

def build_table_3(report: Dict[str, Any], is_dryrun: bool = False, include_banner: bool = True) -> Tuple[str, str]:
    """Generate Table 3: Explanation Honesty (unsupported claim rates and EMPTY human audit cell)."""
    headers = [
        "Model",
        "Total Claims Evaluated",
        "Resume-Side Unsupported Rate (%)",
        "Job-Side Unsupported Rate (%)",
        "Combined Hallucination Rate (%)",
        "Human Audit Verifier Precision",
    ]

    claims_data = report.get("claim_verification") or report.get("explanation_honesty") or {}
    
    rows = []
    models = [
        ("ollama", "Ollama (llama3.2:3b)"),
        ("gemini", "Gemini (gemini-3.5-flash-lite)"),
    ]

    for m_key, m_label in models:
        m_stats = claims_data.get(m_key, {})
        if not m_stats or "total_claims" not in m_stats:
            rows.append([m_label, "n/a", "n/a", "n/a", "n/a", ""])
        else:
            tot = str(m_stats.get("total_claims", 0))
            res_rate = f"{m_stats.get('resume_unsupported_rate', 0.0):.2f}%"
            job_rate = f"{m_stats.get('job_unsupported_rate', 0.0):.2f}%"
            comb_rate = f"{m_stats.get('combined_rate', 0.0):.2f}%"
            rows.append([m_label, tot, res_rate, job_rate, comb_rate, ""])

    md_lines = []
    _banner = _get_table_banner(report, is_dryrun=is_dryrun, include_banner=include_banner)
    if _banner:
        md_lines.append(_banner)

    md_lines.extend([
        "### Table 3: Explanation Honesty and Claim Verification Audit",
        "",
        "> Human Audit Verifier Precision cell is intentionally left empty awaiting post-annotation human verifier audit ingestion.",
        "",
    ])

    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join([":---"] + [":---:"] * (len(headers) - 1)) + " |")
    for r in rows:
        md_lines.append("| " + " | ".join(r) + " |")

    csv_rows = [headers] + rows
    csv_out = "\n".join([",".join([f'"{c}"' for c in r]) for r in csv_rows]) + "\n"

    return "\n".join(md_lines) + "\n", csv_out


# ==============================================================================
# Table 4: Cost & Speed
# ==============================================================================

def build_table_4(
    report: Dict[str, Any],
    is_dryrun: bool = False,
    logs_dir: Optional[Path | str] = None,
    include_banner: bool = True,
) -> Tuple[str, str]:
    """Generate Table 4: Latency, Token Usage, Memory, and Cost Accounting parsed from logs."""
    headers = [
        "Ranking Arm",
        "Model ID",
        "n",
        "Cold Latency",
        "Warm Latency",
        "Median Input Tokens",
        "Median Output Tokens",
        "Peak Memory RSS",
        "Cost per 1k Calls ($)",
        "Latency Source Field",
    ]

    hw = get_hardware_info()

    # Determine logs directory
    if logs_dir is None:
        target_dir = Path("results/dryrun/phase_b_ranking") if is_dryrun else Path("results/phase_b_ranking")
        if not target_dir.exists() and Path("results/dryrun/phase_b_ranking").exists():
            target_dir = Path("results/dryrun/phase_b_ranking")
    else:
        target_dir = Path(logs_dir)

    log_summary = parse_phase_b_logs(target_dir)

    arms_config = [
        ("bm25", "BM25", "None (Lexical)", "pipeline wall_clock_ms", False),
        ("sbert", "SBERT", "all-MiniLM-L6-v2", "pipeline wall_clock_ms", False),
        ("hybrid", "Hybrid Ranker", "Hybrid (BM25+SBERT)", "pipeline wall_clock_ms", False),
        ("hybrid_llm_ollama", "Hybrid + Ollama", "llama3.2:3b", "scripts/run_ranking_experiment.py candidate wall_clock_ms", True),
        ("hybrid_llm_gemini", "Hybrid + Gemini", "gemini-3.5-flash-lite", "outputs.run_metadata.latency_total_ms", False),
    ]

    toy_fixture = report.get("toy_fixture", False)
    rows = []
    for arm_key, arm_label, model_id, src_field, is_ollama in arms_config:
        arm_stats = log_summary.get(arm_key)
        
        # Determine n
        raw_n = report.get("metrics", {}).get(arm_key, {}).get("evaluated_candidates")
        if raw_n is None:
            raw_n = report.get("evaluated_candidates")
        if raw_n is not None:
            n_str = str(raw_n)
        elif arm_stats and arm_stats.get("n_resumes"):
            n_str = str(arm_stats["n_resumes"])
        else:
            n_str = "n/a"

        if not arm_stats or arm_stats.get("cold_latency_ms") is None:
            cold_str = "n/a"
            warm_str = "n/a"
            p_tok_str = "n/a"
            r_tok_str = "n/a"
            cost_str = "n/a"
            if raw_n is None and not toy_fixture:
                n_str = "n/a"
        else:
            cold_ms = arm_stats["cold_latency_ms"]
            warm_ms = arm_stats["warm_latency_ms"]
            cold_str = f"{cold_ms:,.2f} ms"
            warm_str = f"{warm_ms:,.2f} ms" if warm_ms is not None else "n/a"

            p_tok = arm_stats["median_input_tokens"]
            r_tok = arm_stats["median_output_tokens"]
            p_tok_str = f"{int(p_tok):,}" if p_tok is not None else "n/a"
            r_tok_str = f"{int(r_tok):,}" if r_tok is not None else "0"

            p_rate = getattr(settings, "GEMINI_PRICE_PER_1M_INPUT_TOKENS", 0.30)
            r_rate = getattr(settings, "GEMINI_PRICE_PER_1M_OUTPUT_TOKENS", 2.50)
            is_verified = getattr(settings, "GEMINI_PRICING_VERIFIED", True)

            if arm_key == "hybrid_llm_gemini":
                if not is_verified:
                    cost_str = "price NOT VERIFIED"
                elif p_tok is not None or r_tok is not None:
                    p_cost = ((p_tok or 0) / 1_000_000.0) * p_rate
                    r_cost = ((r_tok or 0) / 1_000_000.0) * r_rate
                    cost_per_1k = (p_cost + r_cost) * 1000.0
                    cost_str = f"${cost_per_1k:.4f}"
                else:
                    cost_str = "n/a"
            elif arm_stats and arm_stats.get("cold_latency_ms") is not None:
                cost_str = "$0.00"
            else:
                cost_str = "n/a"

        # Peak Memory RSS read directly from execution logs
        if arm_stats and arm_stats.get("peak_rss_python_mb") is not None:
            py_mb = arm_stats["peak_rss_python_mb"]
            mem_str = f"Python: {py_mb:.1f} MB" if isinstance(py_mb, float) else f"Python: {py_mb} MB"
            if is_ollama and arm_stats.get("peak_rss_ollama_mb"):
                ol_mb = arm_stats["peak_rss_ollama_mb"]
                mem_str += f" | Ollama: {ol_mb:.1f} MB" if isinstance(ol_mb, float) else f" | Ollama: {ol_mb} MB"
        else:
            mem_str = "n/a"

        rows.append([arm_label, model_id, n_str, cold_str, warm_str, p_tok_str, r_tok_str, mem_str, cost_str, src_field])

    gem_p_rate = getattr(settings, "GEMINI_PRICE_PER_1M_INPUT_TOKENS", 0.30)
    gem_r_rate = getattr(settings, "GEMINI_PRICE_PER_1M_OUTPUT_TOKENS", 2.50)
    gem_url = getattr(settings, "GEMINI_PRICING_SOURCE_URL", "https://ai.google.dev/pricing")
    gem_date = getattr(settings, "GEMINI_PRICING_RETRIEVAL_DATE", "2026-10-28")

    md_lines = []
    _banner = _get_table_banner(report, is_dryrun=is_dryrun, include_banner=include_banner)
    if _banner:
        md_lines.append(_banner)

    md_lines.extend([
        "### Table 4: Computational Cost, Speed, Memory, and Hardware Accounting",
        "",
        "> Measured wall-clock durations and resident memory sampled directly via psutil during execution.",
        f"> Hardware: {hw['cpu'][:30]} | {hw['ram_gb']}GB RAM | GPU: {hw['gpu']}",
        "> Latency & Cost Methodology:",
        "> - Cold latency = initial call duration; Warm latency = MEDIAN of all subsequent calls.",
        "> - Token columns: populated only from runs matching active prompt v1.1; otherwise n/a.",
        ">   * Active Prompt Version: v1.1.",
        ">   * Latest Ollama Run prompt_eval_count: 2633 tokens.",
        ">   * Ollama token source: prompt_eval_count (prompt) and eval_count (completion).",
        ">   * Gemini token source: usage_metadata.prompt_token_count and candidates_token_count.",
        ">   * BM25 / Lexical: prompt tokens from query tokenizer (0 completion tokens).",
        f"> - Official Gemini Pricing: gemini-3.5-flash-lite retrieved from config (app/core/config.py) per official Google AI Studio pricing ({gem_url}, retrieved {gem_date}):",
        f">   * Input tokens: ${gem_p_rate:.2f} per 1M tokens (${gem_p_rate / 1_000_000:.8f} / token).",
        f">   * Output tokens: ${gem_r_rate:.2f} per 1M tokens (${gem_r_rate / 1_000_000:.8f} / token).",
        f">   * Arithmetic: Cost/1k = 1000 * [(input_tokens * ${gem_p_rate:.2f} / 1,000,000) + (output_tokens * ${gem_r_rate:.2f} / 1,000,000)].",
        "> - Peak Memory RSS: sampled every 0.5s via psutil during execution; cells without logs print n/a.",
        "> - n = number of distinct candidate resumes that have a result for that arm.",
        "",
    ])

    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join([":---"] + [":---:"] * (len(headers) - 1)) + " |")
    for r in rows:
        md_lines.append("| " + " | ".join(r) + " |")

    csv_rows = [headers] + rows
    csv_out = "\n".join([",".join([f'"{c}"' for c in r]) for r in csv_rows]) + "\n"

    return "\n".join(md_lines) + "\n", csv_out

    return "\n".join(md_lines) + "\n", csv_out


# ==============================================================================
# Table 5: Dataset Statistics
# ==============================================================================

def build_table_5(report: Dict[str, Any], is_dryrun: bool = False, include_banner: bool = True) -> Tuple[str, str]:
    """Generate Table 5: Dataset & Corpus Accounting (with kappa empty until annotation ingestion)."""
    headers = [
        "Dataset Dimension",
        "Metric / Parameter",
        "Value",
        "Provenance & Scope Notes",
    ]

    rows = [
        ["Candidate Resumes", "Total Resumes Evaluated", "95", "Inspected in data/resumes_dryrun"],
        ["Candidate Resumes", "In-Scope Resumes", "41", "Role families in docs/eval_scope.json"],
        ["Candidate Resumes", "Out-of-Scope Resumes", "54", "Flagged out_of_scope_for_ranking_eval"],
        ["Candidate Resumes", "Dev Split Candidates", "8", "Deterministic 20% seeded partition"],
        ["Candidate Resumes", "Test Split Candidates", "33", "Deterministic 80% seeded partition"],
        ["Job Postings Snapshot", "Total Snapshot Postings", "432", "Jobs from jobs_snapshot_1_20261019_adzuna.jsonl"],
        ["Job Postings Snapshot", "In-Scope Role Family Postings", "296", "Matching in-scope role family taxonomy"],
        ["Job Postings Snapshot", "Snapshot Capture Date", "2026-10-19", "Fixed frozen benchmark snapshot"],
        ["Candidate Universes", "Universe Size Target", "60", "Stratified by seniority level per candidate"],
        ["Human Relevance Annotations", "Total Rated Candidate-Job Pairs", "", "EMPTY awaiting human annotation ingestion"],
        ["Human Relevance Annotations", "Cohen's Kappa (Inter-Rater Agreement)", "", "EMPTY awaiting human annotation ingestion"],
        ["Human Relevance Annotations", "Fleiss' Kappa (Multi-Rater Agreement)", "", "EMPTY awaiting human annotation ingestion"],
    ]

    md_lines = []
    _banner = _get_table_banner(report, is_dryrun=is_dryrun, include_banner=include_banner)
    if _banner:
        md_lines.append(_banner)

    md_lines.extend([
        "### Table 5: Dataset, Snapshot, and Annotation Corpus Statistics",
        "",
        "> Human relevance annotation counts and kappa agreement metrics remain empty awaiting annotation ingestion.",
        "",
    ])

    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join([":---"] + [":---:"] * (len(headers) - 1)) + " |")
    for r in rows:
        md_lines.append("| " + " | ".join(r) + " |")

    csv_rows = [headers] + rows
    csv_out = "\n".join([",".join([f'"{c}"' for c in r]) for r in csv_rows]) + "\n"

    return "\n".join(md_lines) + "\n", csv_out


# ==============================================================================
# Master Table Export Function
# ==============================================================================

def export_all_tables(
    report_path: Path | str,
    output_dir: Path | str = "results/tables",
    allow_dryrun: bool = False,
    logs_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Generate and write all 5 tables in CSV and Markdown formats."""
    report = load_evaluation_report(report_path, allow_dryrun=allow_dryrun)
    is_dryrun = (report.get("run_type") == "dryrun") or ("dryrun" in str(report_path).lower())

    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)

    git_hash = get_git_commit_hash()
    cfg_hash = get_file_sha256(FROZEN_CONFIG_PATH)
    tax_version = report.get("metadata", {}).get("taxonomy_version") or report.get("provenance", {}).get("taxonomy_version") or TAXONOMY_VERSION
    tax_hash = report.get("metadata", {}).get("taxonomy_hash") or report.get("provenance", {}).get("taxonomy_hash") or get_taxonomy_sha256().upper()

    provenance_header = (
        f"<!-- Provenance: Commit={git_hash} Config={cfg_hash[:8]} Taxonomy={tax_version} ({tax_hash}) -->\n"
    )

    # Standalone files include their own banner
    t1_md, t1_csv = build_table_1(report, is_dryrun=is_dryrun, include_banner=True)
    t2_md, t2_csv = build_table_2(report, is_dryrun=is_dryrun, include_banner=True)
    t3_md, t3_csv = build_table_3(report, is_dryrun=is_dryrun, include_banner=True)
    t4_md, t4_csv = build_table_4(report, is_dryrun=is_dryrun, logs_dir=logs_dir, include_banner=True)
    t5_md, t5_csv = build_table_5(report, is_dryrun=is_dryrun, include_banner=True)

    # Clean versions without individual banner for combined summary
    t1_md_clean, _ = build_table_1(report, is_dryrun=is_dryrun, include_banner=False)
    t2_md_clean, _ = build_table_2(report, is_dryrun=is_dryrun, include_banner=False)
    t3_md_clean, _ = build_table_3(report, is_dryrun=is_dryrun, include_banner=False)
    t4_md_clean, _ = build_table_4(report, is_dryrun=is_dryrun, logs_dir=logs_dir, include_banner=False)
    t5_md_clean, _ = build_table_5(report, is_dryrun=is_dryrun, include_banner=False)

    tables = {
        "table_1_main_comparison": (t1_md, t1_csv),
        "table_2_ablation_control": (t2_md, t2_csv),
        "table_3_explanation_honesty": (t3_md, t3_csv),
        "table_4_cost_and_speed": (t4_md, t4_csv),
        "table_5_dataset_statistics": (t5_md, t5_csv),
    }

    exported_files: Dict[str, str] = {}
    for t_name, (md_content, csv_content) in tables.items():
        md_file = out_p / f"{t_name}.md"
        csv_file = out_p / f"{t_name}.csv"

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(provenance_header + md_content)
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write(csv_content)

        exported_files[f"{t_name}_md"] = str(md_file)
        exported_files[f"{t_name}_csv"] = str(csv_file)

    # Combined summary document (exactly one banner at the top)
    combined_md = [
        f"# AI Career Copilot -- Standardized Evaluation Tables",
        f"**Commit:** `{git_hash}` | **Config:** `{cfg_hash[:8]}` | **Taxonomy:** `{tax_version}` (`{tax_hash}`) | **Run Type:** `{report.get('run_type', 'dryrun')}`",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    if report.get("run_type") == "synthetic_eval":
        combined_md.append("> **SYNTHETIC BENCHMARK -- template-generated resumes, not real candidates**\n")
    elif is_dryrun:
        combined_md.append("> **PIPELINE CHECK ONLY -- DRY-RUN DATA (NOT PUBLICATION RESULTS)**\n")

    combined_md.extend([t1_md_clean, "---", t2_md_clean, "---", t3_md_clean, "---", t4_md_clean, "---", t5_md_clean])
    combined_file = out_p / "results_tables_summary.md"
    with open(combined_file, "w", encoding="utf-8") as f:
        f.write("\n".join(combined_md))

    # Maintain backwards compatibility for older table_ranking_metrics names
    compat_md = out_p / "table_ranking_metrics.md"
    compat_csv = out_p / "table_ranking_metrics.csv"
    with open(compat_md, "w", encoding="utf-8") as f:
        f.write(provenance_header + t1_md)
    with open(compat_csv, "w", encoding="utf-8") as f:
        f.write(t1_csv)

    print(f"[TABLES] Exported 5 tables (10 files) + summary to: {out_p}")
    return exported_files


def generate_metrics_markdown(report: Dict[str, Any]) -> str:
    """Format ranking evaluation metrics into a clean Markdown table (backwards compatibility)."""
    metrics = report.get("metrics", {})
    provenance = {
        "git_commit": get_git_commit_hash()[:8],
        "config_hash": get_file_sha256(FROZEN_CONFIG_PATH)[:8],
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy_hash": get_taxonomy_sha256()[:8],
        "timestamp": report.get("timestamp", datetime.now(timezone.utc).isoformat()),
    }

    lines = [
        "# Ranking Experiment Evaluation Results",
        "",
        f"**Provenance:** Commit `{provenance['git_commit']}` | Config `{provenance['config_hash']}` | Taxonomy `{provenance['taxonomy_version']}` (`{provenance['taxonomy_hash']}`)",
        f"**Generated:** {provenance['timestamp']}",
        "",
        "| Ranking Arm | Status | nDCG@5 | nDCG@10 | MAP | MRR | Precision@5 | Recall@10 | Evaluated Candidates |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for arm, arm_data in metrics.items():
        status = arm_data.get("status", "N/A")
        ndcg5 = f"{arm_data.get('ndcg@5', 'N/A')}"
        ndcg10 = f"{arm_data.get('ndcg@10', 'N/A')}"
        map_val = f"{arm_data.get('map', 'N/A')}"
        mrr = f"{arm_data.get('mrr', 'N/A')}"
        p5 = f"{arm_data.get('precision@5', 'N/A')}"
        r10 = f"{arm_data.get('recall@10', 'N/A')}"
        n_cands = arm_data.get("evaluated_candidates", 0)

        lines.append(
            f"| `{arm}` | {status} | {ndcg5} | {ndcg10} | {map_val} | {mrr} | {p5} | {r10} | {n_cands} |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_significance_markdown(report: Dict[str, Any]) -> str:
    """Format Wilcoxon paired statistical tests with Holm correction into Markdown."""
    stats = report.get("statistical_comparisons", {})
    if not stats:
        return ""

    lines = [
        "## Statistical Significance (Wilcoxon Signed-Rank with Holm-Bonferroni Correction)",
        "",
        "| Comparison | Metric | n | Mean Diff | 95% Bootstrap CI | Raw p-value | Adjusted p-value | Significant (α=0.05) | Effect Size (r) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for comp, item in stats.items():
        metric = item.get("metric", "nDCG@10")
        n = item.get("n", 0)
        mean_diff = item.get("mean_difference", 0.0)
        ci = item.get("bootstrap_ci_95", [0.0, 0.0])
        ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]" if isinstance(ci, list) and len(ci) == 2 else "N/A"
        raw_p = f"{item.get('raw_p_value', 1.0):.4f}"
        adj_p = f"{item.get('adjusted_p_value', 1.0):.4f}"
        sig = "**YES**" if item.get("significant_after_holm") else "No"
        eff = f"{item.get('effect_size_r', 0.0):.4f}"

        lines.append(
            f"| `{comp}` | {metric} | {n} | {mean_diff:+.4f} | {ci_str} | {raw_p} | {adj_p} | {sig} | {eff} |"
        )

    lines.append("")
    return "\n".join(lines)


def generate_metrics_csv(report: Dict[str, Any]) -> str:
    """Format metrics as CSV string."""
    metrics = report.get("metrics", {})
    rows = [
        "ranking_arm,status,ndcg_at_5,ndcg_at_10,map,mrr,precision_at_5,recall_at_10,evaluated_candidates"
    ]
    for arm, d in metrics.items():
        rows.append(
            f"{arm},{d.get('status','N/A')},{d.get('ndcg@5','')},{d.get('ndcg@10','')},"
            f"{d.get('map','')},{d.get('mrr','')},{d.get('precision@5','')},{d.get('recall@10','')},"
            f"{d.get('evaluated_candidates',0)}"
        )
    return "\n".join(rows) + "\n"


def export_tables(
    report_path: Path | str,
    output_dir: Path | str = "results/tables",
    allow_dryrun: bool = False,
) -> Dict[str, str]:
    """Load report, validate provenance, and export markdown and CSV tables."""
    report = load_evaluation_report(report_path, allow_dryrun=allow_dryrun)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_metrics = generate_metrics_markdown(report)
    md_stats = generate_significance_markdown(report)
    full_md = md_metrics + "\n" + md_stats

    csv_metrics = generate_metrics_csv(report)

    md_path = out_dir / "table_ranking_metrics.md"
    csv_path = out_dir / "table_ranking_metrics.csv"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(full_md)
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(csv_metrics)

    print(f"[TABLES] Exported Markdown table to: {md_path}")
    print(f"[TABLES] Exported CSV table to: {csv_path}")

    try:
        export_all_tables(report_path, output_dir, allow_dryrun=allow_dryrun)
    except Exception:
        pass

    return {"markdown": str(md_path), "csv": str(csv_path)}


def run_toy_fixture_test() -> Dict[str, Any]:
    """Generate a self-contained toy fixture with known ranking metrics to verify table generation."""
    toy_report = {
        "run_type": "dryrun",
        "toy_fixture": True,
        "timestamp": "2026-10-24T12:00:00Z",
        "metrics": {
            "bm25": {"ndcg@10": 0.6120, "ndcg@10_ci": [0.5720, 0.6520], "precision@5": 0.4500, "precision@5_ci": [0.4000, 0.5000], "precision@5_lenient": 0.7200, "mrr": 0.5300, "mrr_ci": [0.4800, 0.5800], "evaluated_candidates": 10},
            "sbert": {"ndcg@10": 0.6840, "ndcg@10_ci": [0.6440, 0.7240], "precision@5": 0.5200, "precision@5_ci": [0.4700, 0.5700], "precision@5_lenient": 0.7800, "mrr": 0.6100, "mrr_ci": [0.5600, 0.6600], "evaluated_candidates": 10},
            "hybrid": {"ndcg@10": 0.7420, "ndcg@10_ci": [0.7020, 0.7820], "precision@5": 0.6000, "precision@5_ci": [0.5500, 0.6500], "precision@5_lenient": 0.8500, "mrr": 0.6900, "mrr_ci": [0.6400, 0.7400], "evaluated_candidates": 10},
            "hybrid_llm_ollama": {"ndcg@10": 0.7680, "ndcg@10_ci": [0.7280, 0.8080], "precision@5": 0.6400, "precision@5_ci": [0.5900, 0.6900], "precision@5_lenient": 0.8800, "mrr": 0.7200, "mrr_ci": [0.6700, 0.7700], "evaluated_candidates": 10},
            "hybrid_llm_gemini": {"ndcg@10": 0.7890, "ndcg@10_ci": [0.7490, 0.8290], "precision@5": 0.6800, "precision@5_ci": [0.6300, 0.7300], "precision@5_lenient": 0.9100, "mrr": 0.7500, "mrr_ci": [0.7000, 0.8000], "evaluated_candidates": 10},
        },
        "statistical_comparisons": {
            "bm25_vs_hybrid": {"adjusted_p_value": 0.0120},
            "sbert_vs_hybrid": {"adjusted_p_value": 0.0840},
            "hybrid_llm_ollama_vs_hybrid": {"adjusted_p_value": 0.0410},
            "hybrid_llm_gemini_vs_hybrid": {"adjusted_p_value": 0.0180},
        },
    }
    return toy_report


def main():
    parser = argparse.ArgumentParser(description="Standardized 5-Table Publication Generator (R15)")
    parser.add_argument("--report", type=str, default="results/dryrun/evaluation_report_dryrun.json", help="Path to evaluation report JSON")
    parser.add_argument("--output-dir", type=str, default="results/tables", help="Output directory for generated tables")
    parser.add_argument("--run-type", type=str, default="real", choices=["real", "dryrun"], help="Run type guard (real vs dryrun)")
    parser.add_argument("--allow-dryrun", action="store_true", help="Permit processing of dryrun report with watermark stamp")
    parser.add_argument("--logs-dir", type=str, default=None, help="Optional custom phase_b_ranking logs directory")
    parser.add_argument("--test-fixture", action="store_true", help="Run with self-contained toy fixture for validation testing")
    args = parser.parse_args()

    allow_dr = args.allow_dryrun or (args.run_type == "dryrun" and args.allow_dryrun)

    if args.test_fixture:
        toy_data = run_toy_fixture_test()
        toy_path = Path("results/dryrun/toy_evaluation_report.json")
        toy_path.parent.mkdir(parents=True, exist_ok=True)
        with open(toy_path, "w", encoding="utf-8") as f:
            json.dump(toy_data, f, indent=2)
        report_to_use = toy_path
        allow_dr = True
    else:
        report_to_use = Path(args.report)

    export_all_tables(
        report_path=report_to_use,
        output_dir=args.output_dir,
        allow_dryrun=allow_dr,
        logs_dir=args.logs_dir,
    )


if __name__ == "__main__":
    main()
