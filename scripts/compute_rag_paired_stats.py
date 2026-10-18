"""Compute paired comparison of router-driven vs fixed retrieval across the 100 RAG queries.

Calculates:
1. Paired bootstrap 95% CI on MRR diff (Router - Fixed)
2. Exact McNemar test on Hit@1
3. Complete list of router-failure cases (where Fixed hits but Router fails)
4. Saves analysis to results/rag_paired_comparison.json
"""

import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List

import numpy as np
from scipy import stats

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath("."))

from scripts.eval_rag_retrieval import (
    QUERIES_FILE,
    evaluate_document_relevance,
    retrieve_fixed_baseline,
    retrieve_router_driven,
)

OUTPUT_FILE = Path("results/rag_paired_comparison.json")


async def main():
    print("=================================================================")
    print("Computing Paired Comparison: Router vs Fixed RAG Retrieval")
    print("=================================================================")

    queries = []
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))

    print(f"Loaded {len(queries)} queries.")

    fixed_mrr = []
    router_mrr = []
    fixed_hit1 = []
    router_hit1 = []
    fixed_hit5 = []
    router_hit5 = []

    per_query_data = []

    for idx, q in enumerate(queries):
        qid = q.get("query_id", f"Q-{idx+1:03d}")
        qtext = q["query_text"]
        cat = q["category"]
        key_facts = q["key_facts"]
        total_facts = max(1, len(key_facts))

        # 1. Fixed
        fixed_docs = await retrieve_fixed_baseline(qtext, top_k=5)
        first_hit_fixed = None
        for r_idx, doc in enumerate(fixed_docs):
            is_rel, _ = evaluate_document_relevance(doc, key_facts)
            if is_rel and first_hit_fixed is None:
                first_hit_fixed = r_idx + 1

        h1_f = 1 if first_hit_fixed == 1 else 0
        h5_f = 1 if (first_hit_fixed and first_hit_fixed <= 5) else 0
        mrr_f = 1.0 / first_hit_fixed if first_hit_fixed else 0.0

        # 2. Router
        router_docs = await retrieve_router_driven(q, top_k=5)
        first_hit_router = None
        for r_idx, doc in enumerate(router_docs):
            is_rel, _ = evaluate_document_relevance(doc, key_facts)
            if is_rel and first_hit_router is None:
                first_hit_router = r_idx + 1

        h1_r = 1 if first_hit_router == 1 else 0
        h5_r = 1 if (first_hit_router and first_hit_router <= 5) else 0
        mrr_r = 1.0 / first_hit_router if first_hit_router else 0.0

        fixed_mrr.append(mrr_f)
        router_mrr.append(mrr_r)
        fixed_hit1.append(h1_f)
        router_hit1.append(h1_r)
        fixed_hit5.append(h5_f)
        router_hit5.append(h5_r)

        per_query_data.append({
            "query_id": qid,
            "query_text": qtext,
            "category": cat,
            "fixed_hit1": h1_f,
            "router_hit1": h1_r,
            "fixed_hit5": h5_f,
            "router_hit5": h5_r,
            "fixed_mrr": mrr_f,
            "router_mrr": mrr_r,
            "mrr_diff": mrr_r - mrr_f,
        })

    # Paired Bootstrap on MRR diff
    mrr_diffs = np.array(router_mrr) - np.array(fixed_mrr)
    mean_mrr_diff = float(np.mean(mrr_diffs))

    rng = np.random.default_rng(42)
    boot_diffs = []
    B = 2000
    n = len(mrr_diffs)
    for _ in range(B):
        idxes = rng.choice(n, size=n, replace=True)
        boot_diffs.append(np.mean(mrr_diffs[idxes]))

    ci_lower = float(np.percentile(boot_diffs, 2.5))
    ci_upper = float(np.percentile(boot_diffs, 97.5))

    # Exact McNemar test on Hit@1
    # Contingency Table:
    #                 Router Hit=1   Router Hit=0
    # Fixed Hit=1         n11            n10
    # Fixed Hit=0         n01            n00
    n11 = sum(1 for f, r in zip(fixed_hit1, router_hit1) if f == 1 and r == 1)
    n10 = sum(1 for f, r in zip(fixed_hit1, router_hit1) if f == 1 and r == 0) # Fixed hit, Router miss
    n01 = sum(1 for f, r in zip(fixed_hit1, router_hit1) if f == 0 and r == 1) # Router hit, Fixed miss
    n00 = sum(1 for f, r in zip(fixed_hit1, router_hit1) if f == 0 and r == 0)

    # Scipy McNemar / binomial test on discordant pairs (n10, n01)
    contingency_table = [[n11, n10], [n01, n00]]
    # exact binomial test on n01 vs n10:
    total_discordant = n10 + n01
    if total_discordant > 0:
        binom_res = stats.binomtest(k=n01, n=total_discordant, p=0.5, alternative="two-sided")
        mcnemar_pvalue = float(binom_res.pvalue)
    else:
        mcnemar_pvalue = 1.0

    # Router-failure cases where Fixed hit at 1 but Router missed at 1
    hit1_router_failures = [
        item for item in per_query_data if item["fixed_hit1"] == 1 and item["router_hit1"] == 0
    ]

    # Router-failure cases where Fixed hit at 5 but Router missed at 5
    hit5_router_failures = [
        item for item in per_query_data if item["fixed_hit5"] == 1 and item["router_hit5"] == 0
    ]

    result = {
        "paired_mrr_comparison": {
            "mean_fixed_mrr": round(float(np.mean(fixed_mrr)), 4),
            "mean_router_mrr": round(float(np.mean(router_mrr)), 4),
            "mean_mrr_diff_router_minus_fixed": round(mean_mrr_diff, 4),
            "paired_bootstrap_95_ci": [round(ci_lower, 4), round(ci_upper, 4)],
            "bootstrap_iterations": B,
        },
        "mcnemar_hit1_test": {
            "contingency_table_fixed_vs_router": {
                "both_hit_n11": n11,
                "fixed_hit_router_miss_n10": n10,
                "router_hit_fixed_miss_n01": n01,
                "both_miss_n00": n00,
            },
            "discordant_pairs_count": total_discordant,
            "exact_pvalue": mcnemar_pvalue,
            "statistically_significant_at_05": bool(mcnemar_pvalue < 0.05),
        },
        "router_failure_cases_hit1": hit1_router_failures,
        "router_failure_cases_hit5": hit5_router_failures,
        "benchmark_design_caveat": (
            "Because queries were written with intent labels, the benchmark has a built-in advantage "
            "for router-driven retrieval: the query phrasing often reflects domain-specific terminology "
            "that aligns closely with the target store's corpus vocabulary."
        ),
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("\n--- Summary Results ---")
    print(f"Mean MRR Diff (Router - Fixed): {mean_mrr_diff:.4f} [95% CI: {ci_lower:.4f}, {ci_upper:.4f}]")
    print(f"McNemar Hit@1: Fixed=1/Router=0: {n10}, Router=1/Fixed=0: {n01}, p-value: {mcnemar_pvalue:.4e}")
    print(f"Router failures at Hit@1: {len(hit1_router_failures)} queries")
    print(f"Router failures at Hit@5: {len(hit5_router_failures)} queries")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
